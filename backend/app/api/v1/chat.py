"""Chat API — LLM conversation for MV creation planning.

Supports:
- POST /chat — regular chat (returns JSON or SSE stream)
- POST /chat with generate_plan=true — runs CrewAI crew
- GET /chat/history — conversation history
- POST /chat/stream — SSE streaming endpoint
"""

from fastapi import APIRouter, Depends, HTTPException, Request  # noqa: F401 — Request used below
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
import json

from app.core.database import get_db
from app.core.llm_client import LLMClient, get_llm
from app.api.v1.auth import get_current_user
from app.models.user import User
from app.models.project import Project
from app.api.v1.deps import get_owned_project

router = APIRouter(tags=["chat"])

# Max messages sent to LLM per request (keeps most-recent context, avoids context overflow).
# Full history is always saved to DB for display purposes.
_LLM_HISTORY_WINDOW = 20


def _trim_for_llm(history: list[dict]) -> list[dict]:
    """Return the last _LLM_HISTORY_WINDOW messages for LLM calls."""
    return history[-_LLM_HISTORY_WINDOW:] if len(history) > _LLM_HISTORY_WINDOW else history


async def _collect_stream(result) -> str:
    """Drain a possibly-streaming LLM response into a plain string."""
    if isinstance(result, str):
        return result
    chunks: list[str] = []
    async for chunk in result:
        chunks.append(chunk)
    return "".join(chunks)


# Direct project fields updated from intent extraction tool results
_INTENT_PROJECT_FIELDS = ("visual_style", "mood", "music_style")

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


# ─── Mock helpers (activated by AIMV_MOCK_CHAT=1) ────────────────────────────

_MOCK_CHAT_REPLIES = [
    (
        "收到！这是一个非常强的反乌托邦主题 🎬\n\n"
        "我帮你梳理了方向：**觉醒 × 同化**——"
        "短发少女 EIKO 在一个所有人都被扑克牌花色抱枕取代头部的世界里觉醒，"
        "最终选择反抗体制、逃离流水线。\n\n"
        "整体风格偏**赛博电影**，配乐用暗调 Synth-Cinematic，92 BPM，带人声。\n\n"
        "准备好了可以直接点击「生成 MV」，我来帮你编排完整分镜！"
    ),
    (
        "配乐方向确认 🎵\n\n"
        "我会为这个 MV 生成以下音轨：\n"
        "- **风格**：Synth-Cinematic × 工业电子\n"
        "- **BPM**：92，低频 Bass 驱动，电子鼓强拍\n"
        "- **人声**：带失真处理的女声吟唱，呼应 EIKO 觉醒意象\n"
        "- **时长**：258s，与视频精确对齐\n\n"
        "音乐将使用 **Suno v4** 模型生成，质量更高、节奏更准确。\n\n"
        "如果对视觉风格还有要求，也可以继续告诉我！"
    ),
    (
        "镜头语言规划完毕 🎥\n\n"
        "7 个分镜将使用以下摄像机方案：\n"
        "- **凝视**：超近景静态 + 极浅景深（Veo 3.1）\n"
        "- **流水线**：顶视跟踪俯拍（Veo 3.1）\n"
        "- **炸弹**：鱼眼监控广角（Grok Video 1）\n"
        "- **崩塌**：手持快切 + 慢动作碎片（Seedance 2.0）\n"
        "- **逃离**：侧跟移动 + 粒子拖尾（Veo 3.1）\n"
        "- **虚空**：360° 环绕缓转（Veo 3.1）\n"
        "- **标志**：极简定格片尾（Veo 3.1）\n\n"
        "色调将以**冷蓝 × 暗金**为主基调，高对比度电影 LUT。\n\n"
        "一切就绪，点击「生成 MV」开始吧！"
    ),
    (
        "好的，风格和情感方向已锁定 ✅\n\n"
        "我会把 7 个镜头分成三幕：\n"
        "- **第一幕（0-130s）**：压迫与同化，扑克人群像，EIKO 初次觉醒\n"
        "- **第二幕（130-210s）**：引爆点，CCTV 炸弹，办公室崩塌\n"
        "- **第三幕（210-258s）**：逃离与自由，红色虚空，EIKO LOGO\n\n"
        "人物、场景细节都已准备好，点「生成 MV」开始！"
    ),
]
_mock_reply_idx = 0


async def _mock_chat_response(project, history: list, db, message: str) -> "ChatResponse":
    global _mock_reply_idx
    reply = _MOCK_CHAT_REPLIES[_mock_reply_idx % len(_MOCK_CHAT_REPLIES)]
    _mock_reply_idx += 1
    history.append({"role": "assistant", "content": reply})
    project.chat_history = history
    await db.commit()
    return ChatResponse(role="assistant", content=reply)


async def _mock_plan_response(project, history: list, db) -> "ChatResponse":
    """Return the project's existing storyboard as a ready-made plan — no LLM call."""
    from app.services.mock_pipeline import _MOCK_STORYBOARD, _MOCK_CHARACTER_BANK, _MOCK_MUSIC_PLAN

    storyboard = project.storyboard or _MOCK_STORYBOARD
    character_bank = project.character_bank or _MOCK_CHARACTER_BANK
    music_plan = (project.style_config or {}).get("music_plan") or _MOCK_MUSIC_PLAN

    plan = {
        "storyboard": storyboard,
        "character_bank": character_bank,
        "music_plan": music_plan,
    }
    project.storyboard = storyboard
    project.character_bank = character_bank
    project.status = "planning"
    style_config = dict(project.style_config or {})
    style_config["music_plan"] = music_plan
    project.style_config = style_config

    n = len(storyboard)
    chars = len(character_bank)
    summary = (
        f"创作方案已生成！\n\n"
        f"**角色**：已定义 {chars} 个（EIKO · 扑克人群像）\n"
        f"**分镜**：共 {n} 个片段\n"
        f"**音乐**：暗调 Synth-Cinematic · 92 BPM · 带人声\n\n"
        f"查看下方分镜方案，准备好后点击「开始生成」！"
    )
    history.append({"role": "assistant", "content": summary})
    project.chat_history = history
    await db.commit()
    return ChatResponse(role="assistant", content=summary, plan=plan)


@router.post("/chat/guest")
async def chat_guest(req: ChatMessage, request: Request):
    """Stateless chat for unauthenticated guests — no project, no persistence."""
    from app.utils.redis_pool import check_rate_limit
    client_ip = request.client.host if request.client else "unknown"
    await check_rate_limit(f"guest_chat:{client_ip}", limit=20, window=60)

    prior = req.history or []
    # Strip system/non-standard roles so LLM client only sees user/assistant
    history = [m for m in prior if m.get("role") in ("user", "assistant")]
    history.append({"role": "user", "content": req.message})

    response_text = await _collect_stream(await get_llm().chat(_trim_for_llm(history), stream=False))
    return ChatResponse(role="assistant", content=response_text)


@router.post("/projects/{project_id}/chat")
async def chat(
    project_id: int,
    req: ChatMessage,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await get_owned_project(project_id, user, db)

    history = project.chat_history or []
    history.append({"role": "user", "content": req.message})

    # --- Plan generation mode ---
    if req.generate_plan:
        from app.config import get_settings as _gs
        if _gs().aimv_mock_chat:
            return await _mock_plan_response(project, history, db)
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

        # Always persist music_plan so run_full_pipeline can use Agent 3's output.
        # Also persist music_analysis (when audio was uploaded) for subtitle export.
        style_config = dict(project.style_config or {})
        changed = False
        if plan.get("music_plan"):
            style_config["music_plan"] = plan["music_plan"]
            changed = True
        if plan.get("music_analysis"):
            style_config["music_analysis"] = plan["music_analysis"]
            changed = True
        if changed:
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

    # --- Mock regular chat ---
    from app.config import get_settings as _gs
    if _gs().aimv_mock_chat:
        return await _mock_chat_response(project, history, db, req.message)

    # --- SSE streaming mode ---
    if req.stream:
        async def event_stream():
            full_text = ""
            try:
                stream = await get_llm().chat(_trim_for_llm(history), stream=True)
                if isinstance(stream, str):
                    yield f"data: {json.dumps({'content': stream})}\n\n"
                    full_text = stream
                else:
                    async for chunk in stream:
                        full_text += chunk
                        yield f"data: {json.dumps({'content': chunk})}\n\n"
                yield f"data: {json.dumps({'done': True})}\n\n"
            finally:
                # Persist history even if client disconnects mid-stream
                if full_text:
                    history.append({"role": "assistant", "content": full_text})
                    project.chat_history = history
                    await db.commit()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # --- Regular mode with intent extraction ---
    # Single LLM call: tool calling returns both intent and response text.
    # Falls back to a second llm.chat() only when the model returns no text
    # (rare — happens when tool_choice forces a tool call with no accompanying reply).
    intent_extracted: dict | None = None
    tool_result, response_text = await get_llm().chat_with_tools(_trim_for_llm(history), _INTENT_TOOLS)

    if tool_result:
        intent_extracted = tool_result
        updated = False
        for field in _INTENT_PROJECT_FIELDS:
            if tool_result.get(field):
                setattr(project, field, tool_result[field])
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
        response_text = await _collect_stream(await get_llm().chat(_trim_for_llm(history), stream=False))

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
    project = await get_owned_project(project_id, user, db)
    return project.chat_history or []
