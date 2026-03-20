"""Compare API — Generate the same shot with multiple models for A/B comparison."""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Task
from app.schemas.project import TaskResponse

router = APIRouter(tags=["compare"])


class CompareRequest(BaseModel):
    prompt: str
    type: str = "video"  # video or music or image
    models: list[str]  # e.g. ["seedance", "veo"] or ["suno", "lyria"]
    params: dict = {}


class CompareResponse(BaseModel):
    compare_group_id: str
    tasks: list[TaskResponse]


@router.post("/projects/{project_id}/compare", response_model=CompareResponse)
async def create_comparison(
    project_id: int,
    req: CompareRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Submit the same prompt to multiple models for A/B comparison."""
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")

    if len(req.models) < 2:
        raise HTTPException(status_code=400, detail="Need at least 2 models to compare")

    import uuid
    group_id = uuid.uuid4().hex[:12]

    tasks = []
    for model_name in req.models:
        task = Task(
            project_id=project.id,
            type=req.type,
            model_name=model_name,
            status="pending",
            params={
                **req.params,
                "prompt": req.prompt,
                "compare_group": group_id,
            },
        )
        db.add(task)
        await db.flush()  # assign task.id without committing
        tasks.append(task)

    await db.commit()  # single batch commit
    for task in tasks:
        await db.refresh(task)

    from app.workers.generation_tasks import run_generation_task
    for task in tasks:
        run_generation_task.delay(task.id)

    return CompareResponse(compare_group_id=group_id, tasks=tasks)


@router.get("/projects/{project_id}/compare/{group_id}")
async def get_comparison(
    project_id: int,
    group_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Get results for a comparison group."""
    from sqlalchemy import cast, String
    result = await db.execute(
        select(Task)
        .join(Project)
        .where(
            Task.project_id == project_id,
            Project.user_id == user.id,
            cast(Task.params["compare_group"], String) == f'"{group_id}"',
        )
    )
    group_tasks = result.scalars().all()

    return {
        "group_id": group_id,
        "tasks": [
            {
                "id": t.id,
                "model_name": t.model_name,
                "status": t.status,
                "quality_score": t.quality_score,
                "result": t.result,
            }
            for t in group_tasks
        ],
    }


@router.post("/projects/{project_id}/compare/{group_id}/pick/{task_id}")
async def pick_winner(
    project_id: int,
    group_id: str,
    task_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """User picks the winning version from a comparison."""
    result = await db.execute(
        select(Task)
        .join(Project)
        .where(Task.id == task_id, Task.project_id == project_id, Project.user_id == user.id)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="Task not found")

    # Mark this task's result as the chosen one
    params = task.params or {}
    params["compare_winner"] = True
    task.params = params
    await db.commit()

    return {"ok": True, "picked_task_id": task_id, "model": task.model_name}
