from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Task
from app.schemas.project import TaskResponse
from app.workers.generation_tasks import run_generation_task
from app.core.model_router import ModelRouter

router = APIRouter(prefix="/projects/{project_id}/generate", tags=["generate"])


class GenerateRequest(BaseModel):
    prompt: str | None = None
    model_override: str | None = None
    params: dict = {}


async def _get_project(project_id: int, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _create_task(
    db: AsyncSession, project: Project, task_type: str, model_name: str, params: dict
) -> Task:
    task = Task(
        project_id=project.id,
        type=task_type,
        model_name=model_name,
        status="pending",
        params=params,
    )
    db.add(task)
    await db.commit()
    await db.refresh(task)
    run_generation_task.delay(task.id)
    return task


@router.post("/image", response_model=TaskResponse)
async def generate_image(
    project_id: int,
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, user, db)
    model = req.model_override or "z-image"
    return await _create_task(db, project, "image", model, req.params)


@router.post("/video", response_model=TaskResponse)
async def generate_video(
    project_id: int,
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, user, db)
    # Model routing: use project style or user override
    model = req.model_override
    if not model:
        model = ModelRouter().route_video(
            style=project.visual_style or "",
            quality="high",
            budget="cloud",
        )
    return await _create_task(db, project, "video", model, req.params)


@router.post("/music", response_model=TaskResponse)
async def generate_music(
    project_id: int,
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, user, db)
    model = req.model_override
    if not model:
        needs_vocal = req.params.get("needs_vocal", False)
        model = ModelRouter().route_music(
            needs_vocal=needs_vocal,
            style=project.music_style or "",
            quality="high",
        )
    return await _create_task(db, project, "music", model, req.params)


@router.post("/compose", response_model=TaskResponse)
async def compose(
    project_id: int,
    req: GenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _get_project(project_id, user, db)
    return await _create_task(db, project, "compose", "ffmpeg", req.params)
