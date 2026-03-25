"""Gallery API — Public showcase of published MV projects."""

from fastapi import APIRouter, Depends, HTTPException, Query, Request
from sqlalchemy import select, func, desc, cast, String
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
    # Use cast to text + equality to avoid NULL/type issues with JSON boolean accessor
    query = select(Project).where(
        Project.status == "done",
        cast(Project.style_config["published"], String) == "true",
    )
    if style:
        query = query.where(Project.visual_style == style)

    query = query.order_by(desc(Project.updated_at))
    total_q = select(func.count()).select_from(query.subquery())
    total = (await db.execute(total_q)).scalar() or 0

    query = query.offset((page - 1) * page_size).limit(page_size)
    result = await db.execute(query)
    projects = result.scalars().all()

    # Batch-fetch thumbnails and final videos in 2 queries (avoids N+1)
    project_ids = [p.id for p in projects]
    thumbs_q = await db.execute(
        select(Media)
        .where(Media.project_id.in_(project_ids), Media.type == "image")
        .order_by(Media.project_id, Media.id)
    )
    thumbs: dict[int, str] = {}
    for m in thumbs_q.scalars().all():
        if m.project_id not in thumbs:
            thumbs[m.project_id] = m.file_url

    videos_q = await db.execute(
        select(Media)
        .where(Media.project_id.in_(project_ids), Media.type == "final_video")
        .order_by(Media.project_id, desc(Media.created_at))
    )
    vids: dict[int, str] = {}
    for m in videos_q.scalars().all():
        if m.project_id not in vids:
            vids[m.project_id] = m.file_url

    items = [
        {
            "id": p.id,
            "title": p.title,
            "visual_style": p.visual_style,
            "mood": p.mood,
            "thumbnail_url": thumbs.get(p.id),
            "video_url": vids.get(p.id),
            "likes": (p.style_config or {}).get("likes", 0),
            "created_at": p.created_at.isoformat(),
        }
        for p in projects
    ]

    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/gallery/{project_id}/like")
async def like_project(
    project_id: int,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Like a published project (no auth required). Rate-limited to 1 per IP per project per hour."""
    from app.utils.redis_pool import check_rate_limit
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"like:{project_id}:{client_ip}", limit=1, window=3600)

    result = await db.execute(
        select(Project).where(Project.id == project_id).with_for_update()
    )
    project = result.scalar_one_or_none()
    if not project or not (project.style_config or {}).get("published"):
        raise HTTPException(status_code=404, detail="Project not found")
    config = project.style_config or {}
    config["likes"] = config.get("likes", 0) + 1
    project.style_config = config
    await db.commit()
    return {"likes": config["likes"]}
