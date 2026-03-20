"""Pipeline API — Full MV generation workflow trigger."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project

router = APIRouter(tags=["pipeline"])


@router.post("/projects/{project_id}/pipeline/start")
async def start_pipeline(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Kick off the full MV generation pipeline for a project.

    Prerequisites: project must have a storyboard (from planning phase).
    """
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    if not project.storyboard:
        raise HTTPException(status_code=400, detail="No storyboard found. Run planning first.")

    from app.workers.generation_tasks import run_full_pipeline
    run_full_pipeline.delay(project.id)

    project.status = "generating"
    await db.commit()

    return {"status": "started", "project_id": project.id}
