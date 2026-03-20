"""Progress notification via Redis Pub/Sub → WebSocket."""

import json
import redis

_redis_client = None


def _get_redis():
    global _redis_client
    if _redis_client is None:
        from app.config import get_settings
        settings = get_settings()
        _redis_client = redis.from_url(settings.redis_url)
    return _redis_client


def notify_progress(project_id: int, task_id: int, task_type: str, status: str, detail: dict | None = None):
    """Push a progress event to the project's WebSocket channel."""
    channel = f"project:{project_id}:progress"
    payload = {
        "task_id": task_id,
        "type": task_type,
        "status": status,
        **(detail or {}),
    }
    _get_redis().publish(channel, json.dumps(payload))
