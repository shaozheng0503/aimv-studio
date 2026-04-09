"""Celery tasks for export / re-encoding."""

import os
import tempfile
from app.workers.celery_app import celery_app
from app.workers.generation_tasks import _get_sync_session  # reuse shared engine

# Retry backoff: 60s, 120s between attempts (max_retries=2 → up to 3 total runs)
_RETRY_COUNTDOWN_BASE = 60


@celery_app.task(bind=True, max_retries=2)
def run_export_task(self, task_id: int):
    from app.models.project import Task, Media
    from app.services.compose_service import ComposeService
    from app.utils.storage import upload_file
    from app.utils.progress import notify_progress

    db = _get_sync_session()
    task = None

    try:
        task = db.query(Task).filter(Task.id == task_id).one()
        task.status = "running"
        db.commit()
        notify_progress(task.project_id, task.id, "export", "running")

        params = task.params or {}
        source = params["source_url"]
        platform = params["platform"]
        compose = ComposeService()

        with tempfile.TemporaryDirectory(prefix=f"export_{task.project_id}_{platform}_") as tmp_dir:
            # Step 1: Re-encode for platform
            current = os.path.join(tmp_dir, "platform.mp4")
            compose.export_for_platform(source, platform, current)

            # Step 2: Burn subtitles if lyrics SRT is available
            if params.get("srt_content"):
                srt_file = os.path.join(tmp_dir, "subs.srt")
                with open(srt_file, "w", encoding="utf-8") as f:
                    f.write(params["srt_content"])
                subtitled = os.path.join(tmp_dir, "subtitled.mp4")
                compose.add_subtitles(current, srt_file, subtitled)
                current = subtitled

            # Step 3: Add watermark if requested
            if params.get("add_watermark"):
                watermarked = os.path.join(tmp_dir, "watermarked.mp4")
                compose.add_watermark(current, params.get("watermark_text", "AIMV"), watermarked)
                current = watermarked

            # Step 4: Upload to storage (must happen inside the context manager)
            file_url = upload_file(current, "video/mp4")

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
        if task is not None:
            task.retry_count = (task.retry_count or 0) + 1
            task.error_message = str(e)

            is_final_attempt = self.request.retries >= self.max_retries
            if is_final_attempt:
                # No more retries — mark permanently failed
                task.status = "failed"
                db.commit()
                notify_progress(
                    task.project_id, task.id, "export", "failed", {"error": str(e)}
                )
            else:
                # Will retry — persist error_message + retry_count without flipping to "failed"
                db.commit()

        countdown = _RETRY_COUNTDOWN_BASE * (self.request.retries + 1)
        raise self.retry(exc=e, countdown=countdown)

    finally:
        db.close()
