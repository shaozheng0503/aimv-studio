"""Shared FastAPI dependencies for v1 API routes."""

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.project import Project
from app.models.user import User


async def get_owned_project(project_id: int, user: User, db: AsyncSession) -> Project:
    """Load a project by id, enforcing ownership. Raises 404 if not found."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project
