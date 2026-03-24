"""Export API — Re-encode final MV for different platforms."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Task, Media

router = APIRouter(tags=["export"])

PLATFORM_PRESETS = {
    "douyin": {"label": "Douyin (9:16 vertical)", "width": 1080, "height": 1920, "bitrate": "4M"},
    "bilibili": {"label": "Bilibili (16:9)", "width": 1920, "height": 1080, "bitrate": "6M"},
    "youtube": {"label": "YouTube (16:9 HQ)", "width": 1920, "height": 1080, "bitrate": "8M"},
    "xiaohongshu": {"label": "Xiaohongshu (3:4)", "width": 1080, "height": 1440, "bitrate": "4M"},
    "instagram": {"label": "Instagram Reels (9:16)", "width": 1080, "height": 1920, "bitrate": "3.5M"},
    "original": {"label": "Original (no re-encode)", "width": 0, "height": 0, "bitrate": "0"},
}


class ExportRequest(BaseModel):
    platform: str = "bilibili"
    add_watermark: bool = False
    watermark_text: str = "Made with AIMV"
    add_subtitles: bool = False


@router.get("/export/presets")
async def list_presets():
    return PLATFORM_PRESETS


@router.post("/projects/{project_id}/export")
async def export_video(
    project_id: int,
    req: ExportRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    # Find the final video
    media_result = await db.execute(
        select(Media)
        .where(Media.project_id == project_id, Media.type == "final_video")
        .order_by(Media.created_at.desc())
    )
    final_media = media_result.scalar_one_or_none()
    if not final_media:
        raise HTTPException(status_code=400, detail="No final video found. Run pipeline first.")

    if req.platform == "original":
        return {"download_url": final_media.file_url, "platform": "original"}

    # Build SRT content from stored lyrics if subtitles requested
    srt_content: str | None = None
    if req.add_subtitles:
        lyrics_data = (project.style_config or {}).get("music_analysis", {}).get("lyrics", [])
        if lyrics_data:
            from app.core.music_analyzer import MusicAnalysis, LyricLine
            _lyric_fields = {"text", "start", "end"}
            dummy = MusicAnalysis()
            dummy.lyrics = [
                LyricLine(**{k: v for k, v in l.items() if k in _lyric_fields})
                for l in lyrics_data
                if isinstance(l, dict)
            ]
            srt_content = dummy.to_srt() or None

    # Create export task — output path generated in the worker via tempfile
    task = Task(
        project_id=project.id,
        type="export",
        model_name="ffmpeg",
        params={
            "source_url": final_media.file_url,
            "platform": req.platform,
            "add_watermark": req.add_watermark,
            "watermark_text": req.watermark_text,
            "srt_content": srt_content,
        },
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)

    from app.workers.export_tasks import run_export_task
    run_export_task.delay(task.id)

    return {"task_id": task.id, "platform": req.platform, "status": "processing"}
