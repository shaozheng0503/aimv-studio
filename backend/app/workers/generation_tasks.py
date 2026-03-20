"""Celery tasks for AI content generation.

Each task runs in a worker process:
1. Loads task record from DB
2. Routes to the correct model adapter
3. Runs generation with verify-retry loop
4. Uploads result to object storage
5. Updates task status
"""

import asyncio
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
        _engine = create_engine(sync_url)
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

        # Build character bank from project
        char_bank = CharacterBank(project.character_bank) if project.character_bank else None

        params = task.params or {}
        prompt = params.get("prompt", "")
        character_name = params.get("character_name", "")

        # Route by task type
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
            # Loudness normalization (-14 LUFS) happens during compose (merge_audio_video)

        elif task.type == "compose":
            from app.services.compose_service import ComposeService
            from app.utils.storage import upload_file
            import os
            compose = ComposeService()
            video_paths = params.get("video_paths", [])
            audio_path = params.get("audio_path", "")
            output_path = params.get("output_path", f"/tmp/mv_{project.id}.mp4")
            concat_path = f"/tmp/concat_{project.id}.mp4"

            if video_paths:
                compose.concat_videos(video_paths, concat_path)
                if audio_path:
                    compose.merge_audio_video(concat_path, audio_path, output_path)
                else:
                    output_path = concat_path

            # Upload composed video to MinIO for persistent access
            final_path = output_path if os.path.exists(output_path) else concat_path
            if os.path.exists(final_path):
                notify_progress(project.id, task.id, "compose", "uploading")
                minio_url = upload_file(final_path, "video/mp4")
                # Clean up temp files
                for p in {output_path, concat_path}:
                    try:
                        if os.path.exists(p):
                            os.unlink(p)
                    except OSError:
                        pass
            else:
                minio_url = output_path  # fallback

            from app.adapters.base import GenerateResult
            result = GenerateResult(file_url=minio_url, metadata={"composed": True, "segments": len(video_paths)})

        else:
            raise ValueError(f"Unknown task type: {task.type}")

        # Store result
        task.status = "completed"
        task.result = result.metadata
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
        notify_progress(project.id, task.id, task.type, "completed", {
            "file_url": result.file_url,
            "quality_score": result.metadata.get("quality_score"),
        })

    except Exception as e:
        if task is not None:
            task.status = "failed"
            task.error_message = str(e)
            task.retry_count = (task.retry_count or 0) + 1
            db.commit()
            notify_progress(task.project_id, task.id, task.type, "failed", {"error": str(e)})
        raise self.retry(exc=e)

    finally:
        db.close()


@celery_app.task
def run_full_pipeline(project_id: int):
    """Run the complete MV generation pipeline for a project.

    Flow:
    1. Generate images (keyframes) — parallel per segment
    2. Generate music — parallel with images
    3. Generate video clips — sequential with sing/story routing + frame-chaining
    4. Compose final MV (concat videos + merge audio)
    """
    from app.models.project import Project, Task, Media
    from app.core.shot_router import ShotRouter
    from app.utils.progress import notify_progress

    db = _get_sync_session()
    shot_router = ShotRouter()

    try:
        project = db.query(Project).filter(Project.id == project_id).one()
        storyboard = project.storyboard or []

        if not storyboard:
            return {"error": "No storyboard found. Run planning first."}

        project.status = "generating"
        db.commit()
        notify_progress(project_id, 0, "pipeline", "started", {"total_segments": len(storyboard)})

        # --- Phase 1: Keyframe images + music (parallel) ---
        model_prefs = project.model_preferences or {}
        image_model = model_prefs.get("image", "z-image")

        # Batch-add all image tasks + music task, then single commit
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
            db.flush()  # get task.id without committing
            image_tasks.append(task)

        style_cfg = project.style_config or {}
        music_params = style_cfg.get("music_plan", {})
        # User model preference > crew recommendation > default
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

        db.commit()  # single commit for all Phase 1 tasks
        for task in image_tasks:
            db.refresh(task)
        db.refresh(music_task)

        image_task_ids = [t.id for t in image_tasks]
        for task in image_tasks:
            run_generation_task.delay(task.id)
        run_generation_task.delay(music_task.id)

        # --- Phase 2: Wait for images to complete, then generate videos ---
        # Poll for image task completion (simplified; production would use Celery chords)
        import time
        for _ in range(600):  # max 10 min wait
            db.expire_all()
            pending = db.query(Task).filter(
                Task.id.in_(image_task_ids),
                Task.status.notin_(["completed", "failed"]),
            ).count()
            if pending == 0:
                break
            time.sleep(1)

        notify_progress(project_id, 0, "pipeline", "images_done")

        # Plan shots with sing/story routing
        shot_plans = shot_router.plan_all_shots(storyboard, project.visual_style or "")

        # Collect keyframe image URLs from completed image tasks
        image_media = db.query(Media).filter(
            Media.project_id == project.id,
            Media.type == "image",
        ).order_by(Media.id).all()

        # --- Phase 3: Generate videos sequentially with frame-chaining ---
        video_paths = []
        prev_last_frame = ""
        frame_temp_files: list[str] = []  # track locally extracted frames for cleanup

        for i, plan in enumerate(shot_plans):
            # Use keyframe as first frame (or previous shot's last frame)
            first_frame = prev_last_frame
            if not first_frame and i < len(image_media):
                first_frame = image_media[i].file_url

            # User model preference overrides AI routing
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
                    "label": plan.label,  # sing or story
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

            # Run synchronously (frame-chaining requires sequential execution)
            try:
                run_generation_task(video_task.id)
            except Exception as vid_err:
                notify_progress(project_id, video_task.id, "video", "failed", {
                    "segment": i + 1, "error": str(vid_err)
                })

            # Extract last frame for next shot; skip gracefully on failure
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
                    # else: keep prev_last_frame for next shot continuity

        # Clean up all extracted frame temp files (no longer needed after video generation)
        import os as _os
        if prev_last_frame:
            frame_temp_files.append(prev_last_frame)
        for _f in frame_temp_files:
            try:
                _os.unlink(_f)
            except OSError:
                pass

        notify_progress(project_id, 0, "pipeline", "videos_done")

        # --- Phase 4: Wait for music, then compose ---
        for _ in range(600):
            db.expire_all()
            db.refresh(music_task)
            if music_task.status in ("completed", "failed"):
                break
            time.sleep(1)

        audio_media = db.query(Media).filter(
            Media.task_id == music_task.id, Media.type == "music"
        ).first()

        if video_paths:
            compose_task = Task(
                project_id=project.id,
                type="compose",
                model_name="ffmpeg",
                params={
                    "video_paths": video_paths,
                    "audio_path": audio_media.file_url if audio_media else "",
                    "output_path": f"/tmp/mv_{project.id}.mp4",
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

    except Exception as pipeline_err:
        notify_progress(project_id, 0, "pipeline", "failed", {"error": str(pipeline_err)})
        try:
            project.status = "failed"
            db.commit()
        except Exception:
            pass
        raise

    finally:
        db.close()
