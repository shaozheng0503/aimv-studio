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
llm = LLMClient()


class ChatMessage(BaseModel):
    message: str
    generate_plan: bool = False
    stream: bool = False


class ChatResponse(BaseModel):
    role: str
    content: str
    plan: dict | None = None


async def _load_project(project_id: int, user: User, db: AsyncSession) -> Project:
    result = await db.execute(
        select(Project).where(Project.id == project_id, Project.user_id == user.id)
    )
    project = result.scalar_one_or_none()
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    return project


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
        service = PlanningService()
        plan = await service.generate_plan(
            user_intent=req.message,
            visual_style=project.visual_style or "",
            music_style=project.music_style or "",
            mood=project.mood or "",
        )
        project.storyboard = plan.get("storyboard", [])
        project.character_bank = plan.get("character_bank", {})
        project.status = "planning"

        summary_parts = ["I've created a complete MV plan!\n"]
        if plan.get("character_bank"):
            summary_parts.append(f"**Characters**: {len(plan['character_bank'])} defined")
        if plan.get("storyboard"):
            summary_parts.append(f"**Storyboard**: {len(plan['storyboard'])} segments")
        summary_parts.append("\nReview the plan below. Click **Start Generating** when ready!")
        assistant_msg = "\n".join(summary_parts)

        history.append({"role": "assistant", "content": assistant_msg})
        project.chat_history = history
        await db.commit()
        return ChatResponse(role="assistant", content=assistant_msg, plan=plan)

    # --- SSE streaming mode ---
    if req.stream:
        async def event_stream():
            full_text = ""
            stream = await llm.chat(history, stream=True)
            if isinstance(stream, str):
                # Fallback mode returned a string
                yield f"data: {json.dumps({'content': stream})}\n\n"
                full_text = stream
            else:
                async for chunk in stream:
                    full_text += chunk
                    yield f"data: {json.dumps({'content': chunk})}\n\n"
            yield f"data: {json.dumps({'done': True})}\n\n"

            # Save to history after streaming completes
            history.append({"role": "assistant", "content": full_text})
            project.chat_history = history
            await db.commit()

        return StreamingResponse(event_stream(), media_type="text/event-stream")

    # --- Regular mode ---
    response_text = await llm.chat(history, stream=False)
    if not isinstance(response_text, str):
        # If somehow got a stream, consume it
        chunks = []
        async for chunk in response_text:
            chunks.append(chunk)
        response_text = "".join(chunks)

    history.append({"role": "assistant", "content": response_text})
    project.chat_history = history
    await db.commit()
    return ChatResponse(role="assistant", content=response_text)


@router.get("/projects/{project_id}/chat/history")
async def chat_history(
    project_id: int,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    project = await _load_project(project_id, user, db)
    return project.chat_history or []
