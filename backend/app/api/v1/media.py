"""Media API — File upload (audio/image) + MusicAnalyzer integration."""

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import asyncio
import tempfile
from pathlib import Path

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Media
from app.utils.storage import upload_file

router = APIRouter(tags=["media"])


@router.post("/projects/{project_id}/upload/audio")
async def upload_audio(
    project_id: int,
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload an audio file, store in MinIO, and run MusicAnalyzer."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename or not file.filename.lower().endswith((".mp3", ".wav", ".flac", ".m4a")):
        raise HTTPException(status_code=400, detail="Unsupported audio format. Use MP3/WAV/FLAC/M4A.")
    if file.size and file.size > 100 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Audio file too large. Maximum 100 MB.")

    # Save to temp file — use async UploadFile.read() to avoid blocking the event loop
    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name

    async def _write_upload(dest: str) -> None:
        with open(dest, "wb") as f:
            while True:
                chunk = await file.read(1 << 20)  # 1 MB chunks
                if not chunk:
                    break
                f.write(chunk)

    try:
        await _write_upload(tmp_path)

        # Run music analysis first (CPU-bound, offload to thread pool)
        from app.core.music_analyzer import MusicAnalyzer

        def _analyze(path: str):
            analyzer = MusicAnalyzer(path)
            return analyzer.analyze()

        analysis = await asyncio.to_thread(_analyze, tmp_path)

        # Upload to object storage (sync MinIO client, offload to thread pool)
        content_type = file.content_type or "audio/mpeg"
        file_url = await asyncio.to_thread(upload_file, tmp_path, content_type)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    # Store media record
    media = Media(
        project_id=project.id,
        type="audio",
        file_url=file_url,
        duration=analysis.duration,
        metadata_json={"source": "upload", "filename": file.filename},
    )
    db.add(media)

    # Store analysis in project style_config
    style_config = project.style_config or {}
    style_config["music_analysis"] = analysis.to_dict()
    project.style_config = style_config

    await db.commit()
    await db.refresh(media)

    return {
        "media_id": media.id,
        "file_url": file_url,
        "analysis": analysis.to_dict(),
    }


@router.post("/projects/{project_id}/upload/image")
async def upload_image(
    project_id: int,
    file: UploadFile = File(...),
    character_name: str = "",
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Upload a reference image (e.g. character photo) to the project."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if not file.filename or not file.filename.lower().endswith((".png", ".jpg", ".jpeg", ".webp")):
        raise HTTPException(status_code=400, detail="Unsupported image format.")
    if file.size and file.size > 20 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="Image file too large. Maximum 20 MB.")

    suffix = Path(file.filename).suffix
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = tmp.name

    async def _write_img(dest: str) -> None:
        with open(dest, "wb") as f:
            while True:
                chunk = await file.read(1 << 20)
                if not chunk:
                    break
                f.write(chunk)

    try:
        await _write_img(tmp_path)
        content_type = file.content_type or "image/jpeg"
        file_url = await asyncio.to_thread(upload_file, tmp_path, content_type)
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    media = Media(
        project_id=project.id,
        type="image",
        file_url=file_url,
        metadata_json={"source": "upload", "filename": file.filename, "character_name": character_name},
    )
    db.add(media)

    # Add to character bank if character_name specified
    if character_name:
        char_bank = project.character_bank or {}
        if character_name in char_bank:
            refs = char_bank[character_name].get("reference_images", [])
            refs.append(file_url)
            char_bank[character_name]["reference_images"] = refs
        else:
            char_bank[character_name] = {"name": character_name, "reference_images": [file_url]}
        project.character_bank = char_bank

    await db.commit()
    await db.refresh(media)

    return {"media_id": media.id, "file_url": file_url}


@router.post("/projects/{project_id}/analyze-audio")
async def analyze_audio_only(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Run MusicAnalyzer on already-uploaded project audio. Returns full analysis with lyrics."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    style_config = project.style_config or {}
    existing = style_config.get("music_analysis", {})
    if not existing:
        raise HTTPException(status_code=400, detail="No audio uploaded yet.")

    return existing
