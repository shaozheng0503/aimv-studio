"""Canvas API — save/load VueFlow graph state and dispatch per-shot generation."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Task
from app.models.canvas import Canvas, CanvasShot

router = APIRouter(prefix="/projects/{project_id}/canvas", tags=["canvas"])


# ─── helpers ──────────────────────────────────────────────────────────────────

async def _get_project(project_id: int, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


async def _get_or_create_canvas(project_id: int, db: AsyncSession) -> Canvas:
    result = await db.execute(select(Canvas).where(Canvas.project_id == project_id))
    canvas = result.scalar_one_or_none()
    if not canvas:
        canvas = Canvas(project_id=project_id, nodes=[], edges=[], viewport={})
        db.add(canvas)
        await db.commit()
        await db.refresh(canvas)
    return canvas


# ─── schemas ──────────────────────────────────────────────────────────────────

class CanvasSaveRequest(BaseModel):
    nodes: list[dict]
    edges: list[dict]
    viewport: dict = {}


class ShotGenerateRequest(BaseModel):
    prompt: str
    model_name: str
    duration: float = 5.0
    time_anchor: float | None = None
    canvas_context: dict = {}  # {music, characters, scene, prev_frames}


class CanvasShotResponse(BaseModel):
    id: int
    node_id: str
    prompt: str | None
    model_name: str | None
    duration: float | None
    time_anchor: float | None
    status: str
    task_id: int | None
    video_url: str | None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_media(cls, shot: CanvasShot) -> "CanvasShotResponse":
        return cls(
            id=shot.id,
            node_id=shot.node_id,
            prompt=shot.prompt,
            model_name=shot.model_name,
            duration=shot.duration,
            time_anchor=shot.time_anchor,
            status=shot.status,
            task_id=shot.task_id,
            video_url=shot.media.file_url if shot.media else None,
            created_at=shot.created_at,
            updated_at=shot.updated_at,
        )


class CanvasResponse(BaseModel):
    project_id: int
    nodes: list[dict]
    edges: list[dict]
    viewport: dict
    shots: list[CanvasShotResponse]
    updated_at: datetime

    model_config = {"from_attributes": True}


# ─── endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=CanvasResponse)
async def get_canvas(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Load the canvas graph state and all shot records for a project."""
    await _get_project(project_id, user, db)
    canvas = await _get_or_create_canvas(project_id, db)

    # Load shots with media eagerly
    shots_result = await db.execute(
        select(CanvasShot)
        .where(CanvasShot.canvas_id == canvas.id)
        .order_by(CanvasShot.sort_order)
    )
    shots = shots_result.scalars().all()

    # Resolve media for each shot
    from sqlalchemy.orm import selectinload
    shots_result2 = await db.execute(
        select(CanvasShot)
        .where(CanvasShot.canvas_id == canvas.id)
        .options(selectinload(CanvasShot.media))
        .order_by(CanvasShot.sort_order)
    )
    shots_with_media = shots_result2.scalars().all()

    return CanvasResponse(
        project_id=project_id,
        nodes=canvas.nodes or [],
        edges=canvas.edges or [],
        viewport=canvas.viewport or {},
        shots=[CanvasShotResponse.from_orm_with_media(s) for s in shots_with_media],
        updated_at=canvas.updated_at,
    )


@router.put("", response_model=CanvasResponse)
async def save_canvas(
    project_id: int,
    req: CanvasSaveRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Save the full VueFlow graph (nodes + edges + viewport).
    Also upserts CanvasShot records for every shot-type node.
    """
    await _get_project(project_id, user, db)
    canvas = await _get_or_create_canvas(project_id, db)

    canvas.nodes = req.nodes
    canvas.edges = req.edges
    canvas.viewport = req.viewport

    # Upsert CanvasShot rows for shot nodes
    shot_nodes = [n for n in req.nodes if n.get("type") == "shot"]
    existing_result = await db.execute(
        select(CanvasShot).where(CanvasShot.canvas_id == canvas.id)
    )
    existing_shots: dict[str, CanvasShot] = {
        s.node_id: s for s in existing_result.scalars().all()
    }

    for idx, node in enumerate(shot_nodes):
        node_id = node["id"]
        data = node.get("data", {})
        if node_id in existing_shots:
            shot = existing_shots[node_id]
            # Only update prompt/model/duration if shot hasn't started generating
            if shot.status == "pending":
                shot.prompt = data.get("prompt", shot.prompt)
                shot.model_name = data.get("model", shot.model_name)
                shot.duration = data.get("duration", shot.duration)
                shot.time_anchor = data.get("timeAnchor", shot.time_anchor)
            shot.sort_order = idx
        else:
            shot = CanvasShot(
                project_id=project_id,
                canvas_id=canvas.id,
                node_id=node_id,
                prompt=data.get("prompt"),
                model_name=data.get("model"),
                duration=data.get("duration"),
                time_anchor=data.get("timeAnchor"),
                sort_order=idx,
                status="pending",
            )
            db.add(shot)

    # Remove shots whose nodes were deleted from the canvas
    current_node_ids = {n["id"] for n in shot_nodes}
    for node_id, shot in existing_shots.items():
        if node_id not in current_node_ids and shot.status == "pending":
            await db.delete(shot)

    await db.commit()
    await db.refresh(canvas)

    # Return updated state
    shots_result = await db.execute(
        select(CanvasShot)
        .where(CanvasShot.canvas_id == canvas.id)
        .options(__import__("sqlalchemy.orm", fromlist=["selectinload"]).selectinload(CanvasShot.media))
        .order_by(CanvasShot.sort_order)
    )
    shots = shots_result.scalars().all()

    return CanvasResponse(
        project_id=project_id,
        nodes=canvas.nodes,
        edges=canvas.edges,
        viewport=canvas.viewport or {},
        shots=[CanvasShotResponse.from_orm_with_media(s) for s in shots],
        updated_at=canvas.updated_at,
    )


@router.post("/shots/{node_id}/generate", response_model=CanvasShotResponse)
async def generate_shot(
    project_id: int,
    node_id: str,
    req: ShotGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch generation for a single shot node.
    canvas_context is assembled by the frontend from the connected nodes.
    """
    await _get_project(project_id, user, db)
    canvas = await _get_or_create_canvas(project_id, db)

    # Get or create the CanvasShot record
    shot_result = await db.execute(
        select(CanvasShot).where(
            CanvasShot.canvas_id == canvas.id,
            CanvasShot.node_id == node_id,
        )
    )
    shot = shot_result.scalar_one_or_none()
    if not shot:
        shot = CanvasShot(
            project_id=project_id,
            canvas_id=canvas.id,
            node_id=node_id,
        )
        db.add(shot)

    if shot.status == "generating":
        raise HTTPException(status_code=409, detail="Shot is already generating")

    # Build first_frame_image from prev_frames context if available
    prev_frames = req.canvas_context.get("prev_frames", [])
    first_frame = prev_frames[0]["last_frame_url"] if prev_frames else ""

    # Enrich prompt with canvas context
    context_suffix = _build_context_suffix(req.canvas_context)
    full_prompt = req.prompt + context_suffix if context_suffix else req.prompt

    # Create a Task record and dispatch to Celery
    task = Task(
        project_id=project_id,
        type="video",
        model_name=req.model_name,
        status="pending",
        params={
            "prompt": full_prompt,
            "duration": req.duration,
            "first_frame_image": first_frame,
            "canvas_context": req.canvas_context,
            "node_id": node_id,
        },
    )
    db.add(task)
    await db.flush()

    shot.prompt = req.prompt
    shot.model_name = req.model_name
    shot.duration = req.duration
    shot.time_anchor = req.time_anchor
    shot.status = "generating"
    shot.canvas_context = req.canvas_context
    shot.task_id = task.id

    await db.commit()
    await db.refresh(shot)

    # Dispatch to Celery worker
    from app.workers.generation_tasks import run_generation_task
    run_generation_task.delay(task.id)

    return CanvasShotResponse.from_orm_with_media(shot)


@router.post("/generate-all")
async def generate_all_pending(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch generation for all pending shots in order (respects sort_order)."""
    await _get_project(project_id, user, db)
    canvas = await _get_or_create_canvas(project_id, db)

    shots_result = await db.execute(
        select(CanvasShot)
        .where(CanvasShot.canvas_id == canvas.id, CanvasShot.status == "pending")
        .order_by(CanvasShot.sort_order)
    )
    pending = shots_result.scalars().all()

    if not pending:
        return {"dispatched": 0, "message": "No pending shots"}

    dispatched = 0
    for shot in pending:
        if not shot.prompt:
            continue
        task = Task(
            project_id=project_id,
            type="video",
            model_name=shot.model_name or "veo",
            status="pending",
            params={
                "prompt": shot.prompt,
                "duration": shot.duration or 5.0,
                "canvas_context": shot.canvas_context or {},
                "node_id": shot.node_id,
            },
        )
        db.add(task)
        await db.flush()

        shot.status = "generating"
        shot.task_id = task.id
        dispatched += 1

    await db.commit()

    # Dispatch all at once (parallel generation)
    from app.workers.generation_tasks import run_generation_task
    for shot in pending:
        if shot.task_id:
            run_generation_task.delay(shot.task_id)

    return {"dispatched": dispatched}


@router.get("/shots/{node_id}", response_model=CanvasShotResponse)
async def get_shot_status(
    project_id: int,
    node_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll generation status for a specific shot node."""
    await _get_project(project_id, user, db)
    canvas = await _get_or_create_canvas(project_id, db)

    from sqlalchemy.orm import selectinload
    from sqlalchemy.orm import selectinload as _sil
    result = await db.execute(
        select(CanvasShot)
        .where(CanvasShot.canvas_id == canvas.id, CanvasShot.node_id == node_id)
        .options(_sil(CanvasShot.media))
    )
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    # Sync status from the linked Task so the frontend poll gets live state
    if shot.task_id and shot.status == "generating":
        task_result = await db.execute(select(Task).where(Task.id == shot.task_id))
        task = task_result.scalar_one_or_none()
        if task:
            if task.status == "completed":
                shot.status = "done"
                if not shot.media_id:
                    from app.models.project import Media
                    media_result = await db.execute(
                        select(Media).where(Media.task_id == shot.task_id)
                    )
                    media = media_result.scalar_one_or_none()
                    if media:
                        shot.media_id = media.id
                await db.commit()
                await db.refresh(shot)
            elif task.status == "failed":
                shot.status = "failed"
                await db.commit()

    return CanvasShotResponse.from_orm_with_media(shot)


# ─── internal helpers ──────────────────────────────────────────────────────────

def _build_context_suffix(ctx: dict) -> str:
    """Append human-readable context to the prompt so the model understands style/char constraints."""
    parts = []
    if ctx.get("scene"):
        for s in ctx["scene"]:
            parts.append(f"Scene: {s.get('name', '')} ({s.get('style', '')})")
    if ctx.get("characters"):
        names = [c.get("name", "") for c in ctx["characters"]]
        parts.append(f"Characters: {', '.join(names)}")
    if ctx.get("music"):
        for m in ctx["music"]:
            parts.append(f"Mood: {m.get('mood', '')} at {m.get('bpm', '')} BPM")
    return ". " + ". ".join(parts) if parts else ""
