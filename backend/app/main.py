from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.config import get_settings
from app.api.v1 import auth, project, generate, chat, pipeline, media, compare, export, gallery

settings = get_settings()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield
    # Shutdown


app = FastAPI(
    title="AIMV API",
    description="AI Music Video Creation Platform",
    version="0.1.0",
    lifespan=lifespan,
)

from app.core.middleware import ErrorHandlerMiddleware
app.add_middleware(ErrorHandlerMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/api/v1")
app.include_router(project.router, prefix="/api/v1")
app.include_router(generate.router, prefix="/api/v1")
app.include_router(chat.router, prefix="/api/v1")
app.include_router(pipeline.router, prefix="/api/v1")
app.include_router(media.router, prefix="/api/v1")
app.include_router(compare.router, prefix="/api/v1")
app.include_router(export.router, prefix="/api/v1")
app.include_router(gallery.router, prefix="/api/v1")


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.1.0"}


# WebSocket for real-time generation progress
from fastapi import WebSocket, WebSocketDisconnect
import redis.asyncio as aioredis
import asyncio
import json


@app.websocket("/ws/projects/{project_id}/progress")
async def ws_progress(websocket: WebSocket, project_id: int):
    """WebSocket endpoint for real-time generation progress.

    Auth flow: accept the connection first, then expect the client to send
    {"type": "auth", "token": "<jwt>"} as the first message.  This keeps
    tokens out of URLs (access logs, browser history).
    Closes with 4001 on invalid token, 4003 if project not owned by user.
    """
    from app.core.security import decode_access_token
    from app.core.database import async_session
    from app.models.project import Project
    from sqlalchemy import select

    await websocket.accept()
    try:
        # Wait up to 10 s for auth message
        auth_msg = await asyncio.wait_for(websocket.receive_json(), timeout=10.0)
        token = auth_msg.get("token", "") if isinstance(auth_msg, dict) else ""
    except Exception:
        await websocket.close(code=4001)
        return

    user_id = decode_access_token(token)
    if user_id is None:
        await websocket.close(code=4001)
        return

    async with async_session() as db:
        result = await db.execute(
            select(Project.id).where(Project.id == project_id, Project.user_id == user_id)
        )
        if result.scalar_one_or_none() is None:
            await websocket.close(code=4003)
            return

    r = aioredis.from_url(settings.redis_url)
    pubsub = r.pubsub()
    channel = f"project:{project_id}:progress"
    await pubsub.subscribe(channel)
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json(data)
    except WebSocketDisconnect:
        pass
    finally:
        await pubsub.unsubscribe(channel)
        await r.aclose()
