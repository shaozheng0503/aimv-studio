"""Gallery API — Public showcase of published MV projects."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, func, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Media

router = APIRouter(tags=["gallery"])


@router.post("/projects/{project_id}/publish")
async def publish_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Publish a completed project to the gallery."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if project.status != "done":
        raise HTTPException(status_code=400, detail="Project must be completed before publishing")

    config = project.style_config or {}
    config["published"] = True
    config["likes"] = config.get("likes", 0)
    project.style_config = config
    await db.commit()
    return {"ok": True, "message": "Published to gallery!"}


@router.post("/projects/{project_id}/unpublish")
async def unpublish_project(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    config = project.style_config or {}
    config["published"] = False
    project.style_config = config
    await db.commit()
    return {"ok": True}


@router.get("/gallery")
async def list_gallery(
    page: int = Query(1, ge=1),
    page_size: int = Query(12, ge=1, le=50),
    style: str = "",
    db: AsyncSession = Depends(get_db),
):
    """Browse published projects (public, no auth required)."""
    query = select(Project).where(
        Project.status == "done",
        Project.style_config["published"].as_boolean() == True,
    )
    if style:
        query = query.where(Project.visual_style == style)

    query = query.order_by(desc(Project.updated_at))
    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    projects = result.scalars().all()

    items = []
    for p in projects:
        # Get thumbnail (first image) and final video
        thumb_q = await db.execute(
            select(Media).where(Media.project_id == p.id, Media.type == "image").limit(1)
        )
        thumb = thumb_q.scalar_one_or_none()
        video_q = await db.execute(
            select(Media).where(Media.project_id == p.id, Media.type == "final_video").order_by(desc(Media.created_at)).limit(1)
        )
        video = video_q.scalar_one_or_none()

        items.append({
            "id": p.id,
            "title": p.title,
            "visual_style": p.visual_style,
            "mood": p.mood,
            "thumbnail_url": thumb.file_url if thumb else None,
            "video_url": video.file_url if video else None,
            "likes": (p.style_config or {}).get("likes", 0),
            "created_at": p.created_at.isoformat(),
        })

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/gallery/{project_id}/like")
async def like_project(
    project_id: int,
    db: AsyncSession = Depends(get_db),
):
    """Like a published project (no auth required for simplicity)."""
    result = await db.execute(select(Project).where(Project.id == project_id))
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    config = project.style_config or {}
    config["likes"] = config.get("likes", 0) + 1
    project.style_config = config
    await db.commit()
    return {"likes": config["likes"]}
