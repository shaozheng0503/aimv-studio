"""Chat API — LLM conversation for MV creation planning.

Supports:
- POST /chat — regular chat (returns JSON or SSE stream)
- POST /chat with generate_plan=true — runs CrewAI crew
- GET /chat/history — conversation history
- POST /chat/stream — SSE streaming endpoint
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.database import get_db
from app.core.llm_client import LLMClient
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project

router = APIRouter(tags=["chat"])
_llm: LLMClient | None = None


def _get_llm() -> LLMClient:
    global _llm
    if _llm is None:
        _llm = LLMClient()
    return _llm

# Intent extraction tool schema for LLM function calling
_INTENT_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "update_project_intent",
            "description": (
                "Extract and persist the user's creative intent for the MV. "
                "Call this whenever you identify style, mood, or story details. "
                "Only pass fields you're confident about from the conversation."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "visual_style": {
                        "type": "string",
                        "enum": ["韩娱", "国风", "赛博朋克", "复古迪斯科", "独立电影", "都市甜酷", "幻想童话"],
                        "description": "Visual aesthetic style for the MV",
                    },
                    "mood": {
                        "type": "string",
                        "enum": ["energetic", "melancholic", "romantic", "epic", "peaceful"],
                        "description": "Overall emotional tone",
                    },
                    "music_style": {
                        "type": "string",
                        "description": "Music genre/style (e.g. 'K-pop', 'Electronic', 'Classical')",
                    },
                    "story_concept": {
                        "type": "string",
                        "description": "Brief summary of the MV narrative or concept",
                    },
                    "ready_to_plan": {
                        "type": "boolean",
                        "description": "True if enough info to generate a full plan now",
                    },
                },
                "required": [],
                "additionalProperties": False,
            },
        },
    }
]


class ChatMessage(BaseModel):
    message: str
    generate_plan: bool = False
    stream: bool = False
    history: list[dict] | None = None  # guest mode: pass prior turns


class ChatResponse(BaseModel):
    role: str
    content: str
    plan: dict | None = None
    intent_extracted: dict | None = None


async def _load_project(project_id: int, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


@router.post("/chat/guest")
async def chat_guest(req: ChatMessage):
    """Stateless chat for unauthenticated guests — no project, no persistence."""
    prior = req.history or []
    # Strip system/non-standard roles so LLM client only sees user/assistant
    history = [m for m in prior if m.get("role") in ("user", "assistant")]
    history.append({"role": "user", "content": req.message})

    response_text = await _get_llm().chat(history, stream=False)
    if not isinstance(response_text, str):
        chunks: list[str] = []
        async for chunk in response_text:
            chunks.append(chunk)
        response_text = "".join(chunks)

    return ChatResponse(role="assistant", content=response_text)


@router.post("/projects/{project_id}/chat")
async def chat(
    project_id: int,
    req: ChatMessage,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _load_project(project_id, user, db)

    history = project.chat_history or []
    history.append({"role": "user", "content": req.message})

    # --- Plan generation mode ---
    if req.generate_plan:
        from app.services.planning_service import PlanningService
        # Use cached analysis from upload (avoids re-downloading from MinIO)
        cached_analysis = (project.style_config or {}).get("music_analysis")

        service = PlanningService()
        plan = await service.generate_plan(
            user_intent=req.message,
            music_analysis=cached_analysis or None,
            visual_style=project.visual_style or "",
            music_style=project.music_style or "",
            mood=project.mood or "",
        )
        project.storyboard = plan.get("storyboard", [])
        project.character_bank = plan.get("character_bank", {})
        project.status = "planning"

        # Persist music analysis so subtitle export can use it later
        if plan.get("music_analysis"):
            style_config = dict(project.style_config or {})
            style_config["music_analysis"] = plan["music_analysis"]
            # Also persist shot-level music plan for pipeline use
            if plan.get("music_plan"):
                style_config["music_plan"] = plan["music_plan"]
            project.style_config = style_config

        summary_parts = ["创作方案已生成！\n"]
        if plan.get("character_bank"):
            summary_parts.append(f"**角色**：已定义 {len(plan['character_bank'])} 个")
        if plan.get("storyboard"):
            summary_parts.append(f"**分镜**：共 {len(plan['storyboard'])} 个片段")
        if plan.get("music_analysis", {}).get("bpm"):
            summary_parts.append(f"**BPM**：{plan['music_analysis']['bpm']:.0f}")
        summary_parts.append("\n查看下方分镜方案，准备好后点击「开始生成」！")
        assistant_msg = "\n".join(summary_parts)

        history.append({"role": "assistant", "content": assistant_msg})
        project.chat_history = history
        await db.commit()
        return ChatResponse(role="assistant", content=assistant_msg, plan=plan)

    # --- SSE streaming mode ---
    if req.stream:
        async def event_stream():
            full_text = ""
            stream = await _get_llm().chat(history, stream=True)
            if isinstance(stream, str):
                yield f"data: {json.dumps({'content': stream})}\n\n"
                full_text = stream
            else:
                async for chunk in stream:
                    full_text += chunk
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

            history.append({"role": "assistant", "content": full_text})
            project.chat_history = history
            await db.commit()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # --- Regular mode with intent extraction ---
    # Single LLM call: tool calling returns both intent and response text.
    # Falls back to a second llm.chat() only when the model returns no text
    # (rare — happens when tool_choice forces a tool call with no accompanying reply).
    intent_extracted: dict | None = None
    tool_result, response_text = await _get_llm().chat_with_tools(history, _INTENT_TOOLS)

    if tool_result:
        intent_extracted = tool_result
        updated = False
        if tool_result.get("visual_style"):
            project.visual_style = tool_result["visual_style"]
            updated = True
        if tool_result.get("mood"):
            project.mood = tool_result["mood"]
            updated = True
        if tool_result.get("music_style"):
            project.music_style = tool_result["music_style"]
            updated = True
        if tool_result.get("story_concept"):
            style_config = dict(project.style_config or {})
            style_config["story_concept"] = tool_result["story_concept"]
            project.style_config = style_config
            updated = True
        if updated:
            await db.flush()

    # If the tool-call turn returned no text, fall back to a plain chat call
    if not response_text:
        response_text = await _get_llm().chat(history, stream=False)
        if not isinstance(response_text, str):
            chunks = []
            async for chunk in response_text:
                chunks.append(chunk)
            response_text = "".join(chunks)

    history.append({"role": "assistant", "content": response_text})
    project.chat_history = history
    await db.commit()
    return ChatResponse(role="assistant", content=response_text, intent_extracted=intent_extracted)


@router.get("/projects/{project_id}/chat/history")
async def chat_history(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _load_project(project_id, user, db)
    return project.chat_history or []
