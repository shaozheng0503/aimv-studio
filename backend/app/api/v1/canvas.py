"""Canvas API — save/load VueFlow graph state and dispatch per-shot generation."""
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.llm_client import get_llm
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project, Task, Media
from app.models.canvas import Canvas, CanvasShot
from app.workers.generation_tasks import run_generation_task
from app.api.v1.deps import get_owned_project

router = APIRouter(prefix="/projects/{project_id}/canvas", tags=["canvas"])


# ─── helpers ──────────────────────────────────────────────────────────────────


async def _get_or_create_canvas(project_id: int, db: AsyncSession) -> Canvas:
    result = await db.execute(select(Canvas).where(Canvas.project_id == project_id))
    canvas = result.scalar_one_or_none()
    if not canvas:
        canvas = Canvas(project_id=project_id, nodes=[], edges=[], viewport={})
        db.add(canvas)
        await db.commit()
        await db.refresh(canvas)
    return canvas


async def _load_shots(canvas_id: int, db: AsyncSession) -> list[CanvasShot]:
    """Load all shots for a canvas, ordered by sort_order, with media pre-loaded."""
    result = await db.execute(
        select(CanvasShot)
        .where(CanvasShot.canvas_id == canvas_id)
        .options(selectinload(CanvasShot.media))
        .order_by(CanvasShot.sort_order)
    )
    return list(result.scalars().all())


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
    error_message: str | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

    @classmethod
    def from_orm_with_media(
        cls,
        shot: CanvasShot,
        error_message: str | None = None,
    ) -> "CanvasShotResponse":
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
            error_message=error_message,
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


class CanvasComposeResponse(BaseModel):
    task_id: int
    status: str
    clips: int
    has_audio: bool


# ─── endpoints ────────────────────────────────────────────────────────────────

@router.get("", response_model=CanvasResponse)
async def get_canvas(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Load the canvas graph state and all shot records for a project."""
    await get_owned_project(project_id, user, db)
    canvas = await _get_or_create_canvas(project_id, db)
    shots = await _load_shots(canvas.id, db)
    return CanvasResponse(
        project_id=project_id,
        nodes=canvas.nodes or [],
        edges=canvas.edges or [],
        viewport=canvas.viewport or {},
        shots=[CanvasShotResponse.from_orm_with_media(s) for s in shots],
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
    await get_owned_project(project_id, user, db)
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
    shots = await _load_shots(canvas.id, db)
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
    await get_owned_project(project_id, user, db)
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
    first_frame = prev_frames[0].get("last_frame_url", "") if prev_frames else ""

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
    run_generation_task.delay(task.id)

    return CanvasShotResponse.from_orm_with_media(shot)


@router.post("/generate-all")
async def generate_all_pending(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch generation for all pending shots in order (respects sort_order)."""
    await get_owned_project(project_id, user, db)
    canvas = await _get_or_create_canvas(project_id, db)

    shots_result = await db.execute(
        select(CanvasShot)
        .where(CanvasShot.canvas_id == canvas.id, CanvasShot.status == "pending")
        .order_by(CanvasShot.sort_order)
    )
    pending = shots_result.scalars().all()

    if not pending:
        return {"dispatched": 0, "message": "No pending shots"}

    dispatched: list[CanvasShot] = []
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
        dispatched.append(shot)

    await db.commit()

    # Dispatch all at once (parallel generation)
    for shot in dispatched:
        run_generation_task.delay(shot.task_id)

    return {"dispatched": len(dispatched), "node_ids": [s.node_id for s in dispatched]}


@router.post("/compose", response_model=CanvasComposeResponse)
async def compose_canvas_videos(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Compose all generated shot clips on the canvas into one final video."""
    await get_owned_project(project_id, user, db)
    canvas = await _get_or_create_canvas(project_id, db)

    shots_result = await db.execute(
        select(CanvasShot)
        .where(CanvasShot.canvas_id == canvas.id)
        .options(selectinload(CanvasShot.media))
        .order_by(CanvasShot.sort_order, CanvasShot.id)
    )
    shots = shots_result.scalars().all()
    video_paths = [
        s.media.file_url
        for s in shots
        if s.status == "done" and s.media and s.media.file_url
    ]

    if not video_paths:
        raise HTTPException(status_code=400, detail="No generated shot videos available for compose")

    music_task_result = await db.execute(
        select(Task)
        .where(
            Task.project_id == project_id,
            Task.type == "music",
            Task.status == "completed",
        )
        .order_by(Task.id.desc())
        .limit(1)
    )
    music_task = music_task_result.scalar_one_or_none()
    audio_url = ""
    if music_task:
        media_result = await db.execute(
            select(Media)
            .where(Media.task_id == music_task.id, Media.type == "music")
            .limit(1)
        )
        audio_media = media_result.scalar_one_or_none()
        if audio_media and audio_media.file_url:
            audio_url = audio_media.file_url

    compose_task = Task(
        project_id=project_id,
        type="compose",
        model_name="ffmpeg",
        status="pending",
        params={
            "source": "canvas",
            "video_paths": video_paths,
            "audio_path": audio_url,
        },
    )
    db.add(compose_task)
    await db.flush()
    task_id = compose_task.id
    await db.commit()

    run_generation_task.delay(task_id)
    return CanvasComposeResponse(
        task_id=task_id,
        status="pending",
        clips=len(video_paths),
        has_audio=bool(audio_url),
    )


@router.get("/shots/{node_id}", response_model=CanvasShotResponse)
async def get_shot_status(
    project_id: int,
    node_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll generation status for a specific shot node."""
    await get_owned_project(project_id, user, db)
    canvas = await _get_or_create_canvas(project_id, db)

    result = await db.execute(
        select(CanvasShot)
        .where(CanvasShot.canvas_id == canvas.id, CanvasShot.node_id == node_id)
        .options(selectinload(CanvasShot.media))
    )
    shot = result.scalar_one_or_none()
    if not shot:
        raise HTTPException(status_code=404, detail="Shot not found")

    # Sync status from the linked Task so the frontend poll gets live state
    error_message: str | None = None
    if shot.task_id and shot.status == "generating":
        task_result = await db.execute(select(Task).where(Task.id == shot.task_id))
        task = task_result.scalar_one_or_none()
        if task:
            if task.status == "completed":
                shot.status = "done"
                if not shot.media_id:
                    media_result = await db.execute(
                        select(Media).where(Media.task_id == shot.task_id)
                    )
                    media = media_result.scalar_one_or_none()
                    if media:
                        shot.media_id = media.id
                await db.commit()
                # Re-query with selectinload — db.refresh() only reloads columns,
                # leaving the `media` relationship expired → MissingGreenlet in async.
                refreshed = await db.execute(
                    select(CanvasShot)
                    .where(CanvasShot.id == shot.id)
                    .options(selectinload(CanvasShot.media))
                )
                shot = refreshed.scalar_one()
            elif task.status == "failed":
                shot.status = "failed"
                error_message = task.error_message
                await db.commit()
    elif shot.task_id and shot.status == "failed":
        task_result = await db.execute(select(Task).where(Task.id == shot.task_id))
        task = task_result.scalar_one_or_none()
        if task:
            error_message = task.error_message

    return CanvasShotResponse.from_orm_with_media(shot, error_message=error_message)


class MusicGenerateRequest(BaseModel):
    node_id: str
    description: str = ""
    lyrics: str = ""
    bpm: float = 0
    duration: float = -1
    vocal_language: str = "unknown"
    instrumental: bool = False
    model_name: str = "acestep"


@router.post("/music/generate")
async def generate_music_node(
    project_id: int,
    req: MusicGenerateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Dispatch music generation for a Song node on the canvas."""
    await get_owned_project(project_id, user, db)

    task = Task(
        project_id=project_id,
        type="music",
        model_name=req.model_name or "acestep",
        status="pending",
        params={
            "node_id": req.node_id,
            "prompt": req.description or "cinematic music",
            "description": req.description,
            "lyrics": req.lyrics,
            "bpm": req.bpm,
            "duration": req.duration,
            "vocal_language": req.vocal_language,
            "instrumental": req.instrumental,
        },
    )
    db.add(task)
    await db.flush()        # assigns task.id before expiry on commit
    task_id = task.id
    await db.commit()

    run_generation_task.delay(task_id)
    return {"task_id": task_id, "node_id": req.node_id, "status": "pending"}


@router.get("/music/{node_id}")
async def get_music_node_status(
    project_id: int,
    node_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Poll ACE-Step generation status for a Song node."""
    await get_owned_project(project_id, user, db)

    result = await db.execute(
        select(Task)
        .where(
            Task.project_id == project_id,
            Task.type == "music",
            Task.params.op('->>')('node_id') == node_id,
        )
        .order_by(Task.id.desc())
        .limit(1)
    )
    task = result.scalar_one_or_none()
    if not task:
        raise HTTPException(status_code=404, detail="No music task for this node")

    audio_url = None
    if task.status == "completed":
        media_result = await db.execute(
            select(Media).where(Media.task_id == task.id)
        )
        media = media_result.scalar_one_or_none()
        if media:
            audio_url = media.file_url

    return {
        "task_id": task.id,
        "node_id": node_id,
        "status": task.status,
        "audio_url": audio_url,
        "error": task.error_message,
    }


class PromptSuggestRequest(BaseModel):
    shot_index: int = 1
    canvas_context: dict = {}   # same structure as ShotGenerateRequest.canvas_context
    existing_prompt: str = ""   # current prompt (may be empty)


class PromptOptimizeRequest(BaseModel):
    prompt: str
    type: str = "video"  # video | music_desc | music_lyrics | character | scene


@router.post("/prompt-suggest")
async def suggest_prompt(
    project_id: int,
    req: PromptSuggestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Use LLM to generate a shot prompt from canvas context."""
    await get_owned_project(project_id, user, db)

    ctx = req.canvas_context
    parts: list[str] = []
    if ctx.get("music"):
        for m in ctx["music"]:
            parts.append(f"音乐情绪: {m.get('mood','')} BPM:{m.get('bpm','')}")
    if ctx.get("characters"):
        for c in ctx["characters"]:
            parts.append(f"角色: {c.get('name','')} (LoRA:{c.get('lora_id','')})")
    if ctx.get("scene"):
        for s in ctx["scene"]:
            parts.append(f"场景: {s.get('name','')} 风格:{s.get('style','')} 灯光:{s.get('lighting','')}")
    if ctx.get("prev_frames"):
        parts.append(f"前置镜头数: {len(ctx['prev_frames'])}个")

    context_str = "\n".join(parts) if parts else "无特定上下文"
    existing = f"\n当前草稿prompt：{req.existing_prompt}" if req.existing_prompt else ""

    system_msg = (
        "你是一位专业 MV 导演和 AI 视频生成专家。"
        "根据给定的画布上下文，为指定镜头生成一段简洁有画面感的英文 video generation prompt。"
        "要求：纯英文，50词以内，包含主体动作、镜头语言、光线氛围，不要包含解释性文字。"
    )
    user_msg = (
        f"镜头序号: #{req.shot_index}\n"
        f"上下文信息:\n{context_str}{existing}\n\n"
        "请直接输出 prompt，不要添加任何解释、前缀或引号。"
    )

    try:
        result = await get_llm().chat(
            [{"role": "user", "content": user_msg}],
            system=system_msg,
        )
        return {"prompt": result.strip()}
    except Exception:
        return {
            "prompt": _fallback_suggest_prompt(req),
            "fallback": True,
            "reason": "llm_unavailable",
        }


_OPTIMIZE_PROMPTS: dict[str, tuple[str, str]] = {
    "video": (
        "你是专业 AI 视频生成提示词专家。将用户输入优化为高质量的英文 video prompt。"
        "要求：纯英文，60词以内，包含主体、动作、镜头语言、光线、氛围，去掉冗余词。直接输出优化后的 prompt，不加任何解释。",
        "请优化以下视频提示词：\n{prompt}",
    ),
    "music_desc": (
        "你是专业 AI 音乐生成提示词专家。将用户输入优化为高质量的音乐风格描述，适合 ACEStep/Suno 等模型。"
        "要求：中英文均可，50词以内，包含曲风、乐器、情绪、节奏特征，去掉冗余词。直接输出优化后的描述，不加任何解释。",
        "请优化以下音乐描述提示词：\n{prompt}",
    ),
    "music_lyrics": (
        "你是专业词作人。将用户输入的歌词草稿优化为更有韵律感和画面感的歌词。"
        "保持原有语言（中文/英文），保留原意，增强韵脚和意象。直接输出优化后的歌词，不加任何解释。",
        "请优化以下歌词：\n{prompt}",
    ),
    "character": (
        "你是专业角色设计师。将用户输入优化为清晰的角色视觉描述，适合 AI 图像生成。"
        "要求：中英文均可，40词以内，包含外貌、服装、气质特征。直接输出优化后的描述，不加任何解释。",
        "请优化以下角色描述：\n{prompt}",
    ),
    "scene": (
        "你是专业场景设计师。将用户输入优化为清晰的场景视觉描述，适合 AI 图像/视频生成。"
        "要求：中英文均可，40词以内，包含地点、光线、氛围、视觉风格。直接输出优化后的描述，不加任何解释。",
        "请优化以下场景描述：\n{prompt}",
    ),
}


@router.post("/optimize-prompt")
async def optimize_prompt(
    project_id: int,
    req: PromptOptimizeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Use LLM to optimize a user-written prompt for the given node type."""
    await get_owned_project(project_id, user, db)

    system_msg, user_tpl = _OPTIMIZE_PROMPTS.get(req.type, _OPTIMIZE_PROMPTS["video"])
    user_msg = user_tpl.format(prompt=req.prompt)

    try:
        result = await get_llm().chat(
            [{"role": "user", "content": user_msg}],
            system=system_msg,
        )
        return {"prompt": result.strip()}
    except Exception:
        return {
            "prompt": _fallback_optimize_prompt(req.prompt, req.type),
            "fallback": True,
            "reason": "llm_unavailable",
        }


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


def _fallback_suggest_prompt(req: PromptSuggestRequest) -> str:
    """Best-effort prompt suggestion when remote LLM is unavailable."""
    ctx = req.canvas_context or {}

    subject = "a singer"
    if ctx.get("characters"):
        first = ctx["characters"][0]
        subject = first.get("name") or first.get("description") or subject

    scene = "on a cinematic stage"
    if ctx.get("scene"):
        s0 = ctx["scene"][0]
        scene_name = s0.get("name", "").strip()
        style = s0.get("style", "").strip()
        lighting = s0.get("lighting", "").strip()
        scene_parts = [p for p in [scene_name, style, lighting] if p]
        if scene_parts:
            scene = ", ".join(scene_parts)

    mood = "emotional"
    bpm = ""
    if ctx.get("music"):
        m0 = ctx["music"][0]
        mood = m0.get("mood", "") or mood
        bpm_val = m0.get("bpm", "")
        bpm = f", {bpm_val} BPM" if bpm_val else ""

    base = req.existing_prompt.strip() if req.existing_prompt else ""
    if base:
        return (
            f"{base}, cinematic framing, subtle camera movement, "
            f"{mood} atmosphere{bpm}, cohesive color grading"
        )

    return (
        f"{subject} performing in {scene}, medium shot to close-up, "
        f"cinematic camera movement, {mood} atmosphere{bpm}, dramatic lighting, high detail"
    )


def _fallback_optimize_prompt(prompt: str, prompt_type: str) -> str:
    """Best-effort prompt optimization when remote LLM is unavailable."""
    cleaned = " ".join((prompt or "").strip().split())
    if not cleaned:
        return ""

    if prompt_type == "video":
        return (
            f"{cleaned}, cinematic composition, dynamic camera movement, "
            "dramatic lighting, filmic color grading, high detail"
        )
    if prompt_type == "music_desc":
        return f"{cleaned}; clear genre, instrumentation, mood, rhythm, and arrangement cues"
    if prompt_type == "music_lyrics":
        return cleaned
    if prompt_type in {"character", "scene"}:
        return f"{cleaned}, vivid visual details, consistent style"
    return cleaned
