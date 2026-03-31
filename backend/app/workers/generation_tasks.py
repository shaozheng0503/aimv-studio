"""Celery tasks for AI content generation.

Each task runs in a worker process:
1. Loads task record from DB
2. Routes to the correct model adapter
3. Runs generation with verify-retry loop
4. Uploads result to object storage
5. Updates task status

Pipeline flow (chord-based, no polling):
  run_full_pipeline  → dispatches chord([image tasks, music task])
                                        ↓ (chord callback, worker freed)
  run_video_phase    → sequential video generation with frame-chaining
                                        ↓ (.delay())
  run_compose_phase  → FFmpeg concat + audio merge → project done
"""

import asyncio
import time
import tempfile
import os
from celery import chord as celery_chord
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session, sessionmaker

from app.workers.celery_app import celery_app
from app.config import get_settings

# Sync engine for Celery workers (Celery is sync)
_engine = None
_SessionLocal = None


def _get_sync_session() -> Session:
    global _engine, _SessionLocal
    if _engine is None:
        settings = get_settings()
        sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("postgresql+asyncpg", "postgresql")
        _engine = create_engine(sync_url, pool_pre_ping=True, pool_size=5, max_overflow=10)
        _SessionLocal = sessionmaker(bind=_engine)
    return _SessionLocal()


def _run_async(coro):
    """Run an async function from sync Celery context."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


@celery_app.task(bind=True, max_retries=3, default_retry_delay=10)
def run_generation_task(self, task_id: int):
    """Generic generation task dispatcher."""
    from app.models.project import Task, Media, Project
    from app.services.generation_service import GenerationService
    from app.core.character_bank import CharacterBank
    from app.adapters.base import GenerateRequest
    from app.utils.progress import notify_progress

    db = _get_sync_session()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).one()
        task.status = "running"
        db.commit()
        notify_progress(task.project_id, task.id, task.type, "running")

        project = db.query(Project).filter(Project.id == task.project_id).one()
        service = GenerationService()

        char_bank = CharacterBank(project.character_bank) if project.character_bank else None
        params = task.params or {}
        prompt = params.get("prompt", "")
        character_name = params.get("character_name", "")

        if task.type == "image":
            result = _run_async(service.generate_image(
                prompt=prompt,
                model_name=task.model_name or "z-image",
                character_bank=char_bank,
                character_name=character_name,
                params=params,
            ))

        elif task.type == "video":
            result = _run_async(service.generate_video(
                prompt=prompt,
                model_name=task.model_name or "veo",
                first_frame_image=params.get("first_frame_image", ""),
                character_bank=char_bank,
                character_name=character_name,
                params=params,
            ))

        elif task.type == "music":
            result = _run_async(service.generate_music(
                prompt=prompt,
                model_name=task.model_name or "acestep",
                params=params,
            ))

        elif task.type == "compose":
            from app.services.compose_service import ComposeService
            from app.utils.storage import upload_file
            compose = ComposeService()
            video_paths = params.get("video_paths", [])
            audio_path = params.get("audio_path", "")

            if not video_paths:
                raise RuntimeError("Compose task requires at least one video path")

            _fd_out, output_path = tempfile.mkstemp(suffix=".mp4", prefix=f"mv_{project.id}_")
            os.close(_fd_out)
            _fd_cat, concat_path = tempfile.mkstemp(suffix=".mp4", prefix=f"concat_{project.id}_")
            os.close(_fd_cat)

            compose.concat_videos(video_paths, concat_path)
            if audio_path:
                compose.merge_audio_video(concat_path, audio_path, output_path)
            else:
                output_path = concat_path

            final_path = output_path if os.path.exists(output_path) else concat_path
            if os.path.exists(final_path):
                notify_progress(project.id, task.id, "compose", "uploading")
                minio_url = upload_file(final_path, "video/mp4")
                for p in {output_path, concat_path}:
                    try:
                        if os.path.exists(p):
                            os.unlink(p)
                    except OSError:
                        pass
            else:
                raise RuntimeError(f"Compose produced no output file (expected {final_path})")

            from app.adapters.base import GenerateResult
            result = GenerateResult(file_url=minio_url, metadata={"composed": True, "segments": len(video_paths)})

        else:
            raise ValueError(f"Unknown task type: {task.type}")

        task.status = "completed"
        task.result = {"file_url": result.file_url, **result.metadata}
        task.quality_score = result.metadata.get("quality_score")

        media = Media(
            project_id=project.id,
            task_id=task.id,
            type=task.type if task.type != "compose" else "final_video",
            file_url=result.file_url,
            duration=result.duration,
            metadata_json=result.metadata,
        )
        db.add(media)
        db.commit()
        db.refresh(media)

        # If this task was dispatched from a Canvas shot node, sync its status
        node_id = (task.params or {}).get("node_id")
        if node_id and task.type == "video":
            from app.models.canvas import CanvasShot
            canvas_shot = db.query(CanvasShot).filter(CanvasShot.task_id == task.id).first()
            if canvas_shot:
                canvas_shot.status = "done"
                canvas_shot.media_id = media.id
                db.commit()

        notify_progress(project.id, task.id, task.type, "completed", {
            "file_url": result.file_url,
            "quality_score": result.metadata.get("quality_score"),
            **({"node_id": node_id} if node_id else {}),
        })

    except Exception as e:
        if task is not None:
            task.status = "failed"
            task.error_message = str(e)
            task.retry_count = (task.retry_count or 0) + 1
            db.commit()
            node_id = (task.params or {}).get("node_id")
            if node_id and task.type == "video":
                from app.models.canvas import CanvasShot
                canvas_shot = db.query(CanvasShot).filter(CanvasShot.task_id == task.id).first()
                if canvas_shot:
                    canvas_shot.status = "failed"
                    db.commit()
            notify_progress(task.project_id, task.id, task.type, "failed", {
                "error": str(e),
                **({"node_id": node_id} if node_id else {}),
            })
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task
def run_full_pipeline(project_id: int):
    """Phase 0 — Setup task records and dispatch Phase 1 (images + music) as a chord.

    The chord callback (run_video_phase) is invoked automatically by Celery
    once all image and music tasks complete.  This worker is freed immediately
    after dispatching — no polling sleep loops.
    """
    from app.models.project import Project, Task
    from app.utils.progress import notify_progress

    db = _get_sync_session()
    project = None
    try:
        project = db.query(Project).filter(Project.id == project_id).one()
        storyboard = project.storyboard or []

        if not storyboard:
            return {"error": "No storyboard found. Run planning first."}

        project.status = "generating"
        db.commit()
        notify_progress(project_id, 0, "pipeline", "started", {"total_segments": len(storyboard)})

        model_prefs = project.model_preferences or {}
        image_model = model_prefs.get("image", "z-image")

        image_tasks = []
        for segment in storyboard:
            task = Task(
                project_id=project.id,
                type="image",
                model_name=image_model,
                params={
                    "prompt": segment.get("image_prompt", segment.get("description", "")),
                    "character_name": (segment.get("characters") or [""])[0],
                },
            )
            db.add(task)
            db.flush()
            image_tasks.append(task)

        style_cfg = project.style_config or {}
        music_params = style_cfg.get("music_plan", {})
        music_model_name = (
            model_prefs.get("music")
            or music_params.get("model_recommendation")
            or "acestep"
        )
        music_task = Task(
            project_id=project.id,
            type="music",
            model_name=music_model_name,
            params={"prompt": music_params.get("music_prompt", "cinematic background music for music video")},
        )
        db.add(music_task)
        db.flush()
        db.commit()

        for task in image_tasks:
            db.refresh(task)
        db.refresh(music_task)

        # Build chord: all image tasks + music task run in parallel.
        # When ALL complete, run_video_phase is called automatically (worker freed here).
        phase1_task_ids = [t.id for t in image_tasks] + [music_task.id]
        celery_chord(
            [run_generation_task.s(tid) for tid in phase1_task_ids]
        )(run_video_phase.s(project_id))

    except Exception as pipeline_err:
        notify_progress(project_id, 0, "pipeline", "failed", {"error": str(pipeline_err)})
        if project is not None:
            try:
                project.status = "failed"
                db.commit()
            except Exception:
                pass
        raise
    finally:
        db.close()


@celery_app.task
def run_video_phase(_phase1_results, project_id: int):
    """Phase 2 — Sequential video generation with sing/story routing and frame-chaining.

    Called automatically by the chord from run_full_pipeline once all images
    and music are ready.  Videos must be sequential (frame-chaining).
    When done, dispatches run_compose_phase.
    """
    from app.models.project import Project, Task, Media
    from app.core.shot_router import ShotRouter
    from app.utils.progress import notify_progress

    db = _get_sync_session()
    shot_router = ShotRouter()
    project = None

    try:
        project = db.query(Project).filter(Project.id == project_id).one()
        storyboard = project.storyboard or []
        notify_progress(project_id, 0, "pipeline", "images_done")

        model_prefs = project.model_preferences or {}
        shot_plans = shot_router.plan_all_shots(storyboard, project.visual_style or "")

        image_media = db.query(Media).filter(
            Media.project_id == project.id,
            Media.type == "image",
        ).order_by(Media.id).all()

        video_paths = []
        prev_last_frame = ""
        frame_temp_files: list[str] = []

        for i, plan in enumerate(shot_plans):
            first_frame = prev_last_frame
            if not first_frame and i < len(image_media):
                first_frame = image_media[i].file_url

            video_model = model_prefs.get("video") or plan.video_model

            video_task = Task(
                project_id=project.id,
                type="video",
                model_name=video_model,
                params={
                    "prompt": plan.prompt,
                    "character_name": plan.character_name,
                    "first_frame_image": first_frame,
                    "duration": plan.duration,
                    "label": plan.label,
                    "camera_direction": plan.camera_direction,
                },
            )
            db.add(video_task)
            db.commit()
            db.refresh(video_task)

            pct = int((i / len(shot_plans)) * 100)
            notify_progress(project_id, video_task.id, "video", "running", {
                "segment": i + 1,
                "total": len(shot_plans),
                "pct": pct,
                "label": plan.label,
                "model": plan.video_model,
            })

            _max_vid_retries = 3
            for _attempt in range(_max_vid_retries):
                try:
                    run_generation_task(video_task.id)
                    break
                except Exception as vid_err:
                    if _attempt < _max_vid_retries - 1:
                        time.sleep(5 * (_attempt + 1))
                    else:
                        notify_progress(project_id, video_task.id, "video", "failed", {
                            "segment": i + 1, "error": str(vid_err)
                        })

            db.refresh(video_task)
            if video_task.status == "completed":
                video_media = db.query(Media).filter(Media.task_id == video_task.id).first()
                if video_media:
                    video_paths.append(video_media.file_url)
                    last_frame = shot_router.extract_last_frame(video_media.file_url)
                    if last_frame:
                        if prev_last_frame:
                            frame_temp_files.append(prev_last_frame)
                        prev_last_frame = last_frame

        if prev_last_frame:
            frame_temp_files.append(prev_last_frame)
        for _f in frame_temp_files:
            try:
                os.unlink(_f)
            except OSError:
                pass

        notify_progress(project_id, 0, "pipeline", "videos_done")
        run_compose_phase.delay(project_id, video_paths)

    except Exception as err:
        notify_progress(project_id, 0, "pipeline", "failed", {"error": str(err)})
        if project is not None:
            try:
                project.status = "failed"
                db.commit()
            except Exception:
                pass
        raise
    finally:
        db.close()


@celery_app.task
def run_compose_phase(project_id: int, video_paths: list):
    """Phase 3 — Compose final MV: concat video clips + merge audio track.

    Fetches the music Media record from DB, runs compose task directly,
    then marks project as done.
    """
    from app.models.project import Project, Task, Media
    from app.utils.progress import notify_progress

    db = _get_sync_session()
    project = None
    try:
        project = db.query(Project).filter(Project.id == project_id).one()

        # Music task should already be done (it was part of the Phase 1 chord)
        music_task_record = db.query(Task).filter(
            Task.project_id == project_id,
            Task.type == "music",
            Task.status == "completed",
        ).order_by(Task.id.desc()).first()

        audio_media = None
        if music_task_record:
            audio_media = db.query(Media).filter(
                Media.task_id == music_task_record.id,
                Media.type == "music",
            ).first()

        if video_paths:
            compose_task = Task(
                project_id=project.id,
                type="compose",
                model_name="ffmpeg",
                params={
                    "video_paths": video_paths,
                    "audio_path": audio_media.file_url if audio_media else "",
                },
            )
            db.add(compose_task)
            db.commit()
            db.refresh(compose_task)
            notify_progress(project_id, compose_task.id, "compose", "running", {
                "clips": len(video_paths),
                "has_audio": bool(audio_media),
            })
            run_generation_task(compose_task.id)
        else:
            notify_progress(project_id, 0, "pipeline", "warning", {
                "message": "No video clips were generated. Check individual task errors."
            })

        notify_progress(project_id, 0, "pipeline", "completed", {
            "video_count": len(video_paths),
            "has_audio": bool(audio_media),
        })
        project.status = "done"
        db.commit()

    except Exception as err:
        notify_progress(project_id, 0, "pipeline", "failed", {"error": str(err)})
        if project is not None:
            try:
                project.status = "failed"
                db.commit()
            except Exception:
                pass
        raise
    finally:
        db.close()
