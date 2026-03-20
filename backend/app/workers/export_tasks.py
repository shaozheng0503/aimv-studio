"""Celery tasks for export / re-encoding."""

from app.workers.celery_app import celery_app


@celery_app.task(bind=True, max_retries=2)
def run_export_task(self, task_id: int):
    from app.models.project import Task, Media
    from app.services.compose_service import ComposeService
    from app.utils.storage import upload_file
    from app.utils.progress import notify_progress

    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from app.config import get_settings

    settings = get_settings()
    sync_url = settings.database_url.replace("+asyncpg", "+psycopg2").replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(sync_url)
    Session = sessionmaker(bind=engine)
    db = Session()

    try:
        task = db.query(Task).filter(Task.id == task_id).one()
        task.status = "running"
        db.commit()
        notify_progress(task.project_id, task.id, "export", "running")

        params = task.params or {}
        source = params["source_url"]
        platform = params["platform"]
        output_path = params["output_path"]

        compose = ComposeService()

        # Step 1: Re-encode for platform
        compose.export_for_platform(source, platform, output_path)

        # Step 2: Burn subtitles if lyrics SRT is available
        if params.get("srt_content"):
            import tempfile
            srt_file = tempfile.mktemp(suffix=".srt")
            with open(srt_file, "w", encoding="utf-8") as f:
                f.write(params["srt_content"])
            sub_path = output_path.replace(".mp4", "_sub.mp4")
            compose.add_subtitles(output_path, srt_file, sub_path)
            output_path = sub_path

        # Step 3: Add watermark if requested
        if params.get("add_watermark"):
            wm_path = output_path.replace(".mp4", "_wm.mp4")
            compose.add_watermark(output_path, params.get("watermark_text", "AIMV"), wm_path)
            output_path = wm_path

        # Step 3: Upload to storage
        file_url = upload_file(output_path, "video/mp4")

        # Store result
        task.status = "completed"
        task.result = {"file_url": file_url, "platform": platform}
        media = Media(
            project_id=task.project_id,
            task_id=task.id,
            type="final_video",
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
