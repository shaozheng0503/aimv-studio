"""Celery tasks for export / re-encoding."""

import os
import tempfile
from app.workers.celery_app import celery_app
from app.workers.generation_tasks import _get_sync_session  # reuse shared engine


@celery_app.task(bind=True, max_retries=2)
def run_export_task(self, task_id: int):
    from app.models.project import Task, Media
    from app.services.compose_service import ComposeService
    from app.utils.storage import upload_file
    from app.utils.progress import notify_progress

    db = _get_sync_session()
    tmp_files: list[str] = []  # track all temp files for cleanup

    try:
        task = db.query(Task).filter(Task.id == task_id).one()
        task.status = "running"
        db.commit()
        notify_progress(task.project_id, task.id, "export", "running")

        params = task.params or {}
        source = params["source_url"]
        platform = params["platform"]
        output_path = params["output_path"]
        tmp_files.append(output_path)

        compose = ComposeService()

        # Step 1: Re-encode for platform
        compose.export_for_platform(source, platform, output_path)

        # Step 2: Burn subtitles if lyrics SRT is available
        if params.get("srt_content"):
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".srt", encoding="utf-8", delete=False
            ) as srt_f:
                srt_f.write(params["srt_content"])
                srt_file = srt_f.name
            tmp_files.append(srt_file)
            sub_path = output_path.replace(".mp4", "_sub.mp4")
            tmp_files.append(sub_path)
            compose.add_subtitles(output_path, srt_file, sub_path)
            output_path = sub_path

        # Step 3: Add watermark if requested
        if params.get("add_watermark"):
            wm_path = output_path.replace(".mp4", "_wm.mp4")
            tmp_files.append(wm_path)
            compose.add_watermark(output_path, params.get("watermark_text", "AIMV"), wm_path)
            output_path = wm_path

        # Step 4: Upload to storage
        file_url = upload_file(output_path, "video/mp4")

        # Store result
        task.status = "completed"
        task.result = {"file_url": file_url, "platform": platform}
        media = Media(
            project_id=task.project_id,
            task_id=task.id,
            type="export_video",
            file_url=file_url,
            metadata_json={"platform": platform, "export": True},
        )
        db.add(media)
        db.commit()
        notify_progress(task.project_id, task.id, "export", "completed", {"file_url": file_url})

    except Exception as e:
        task.status = "failed"
        task.error_message = str(e)
        db.commit()
        notify_progress(task.project_id, task.id, "export", "failed", {"error": str(e)})
        raise self.retry(exc=e)
    finally:
        db.close()
        # Clean up all temporary files
        for path in tmp_files:
            try:
                if path and os.path.exists(path):
                    os.unlink(path)
            except OSError:
                pass
