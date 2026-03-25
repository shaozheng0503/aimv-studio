"""Shared async Redis connection pool — reused across WebSocket, rate limiting, health checks."""

import redis.asyncio as aioredis

_pool: aioredis.Redis | None = None


def get_async_redis() -> aioredis.Redis:
    global _pool
    if _pool is None:
        from app.config import get_settings
        _pool = aioredis.from_url(get_settings().redis_url, decode_responses=True)
    return _pool


async def close_async_redis() -> None:
    global _pool
    if _pool is not None:
        await _pool.aclose()
        _pool = None


async def check_rate_limit(key: str, limit: int, window: int) -> None:
    """Increment counter for `key`; raise HTTP 429 if count exceeds `limit` within `window` seconds.

    Silently skips if Redis is unavailable so a Redis outage never blocks normal requests.
    """
    from fastapi import HTTPException
    try:
        r = get_async_redis()
        pipe = r.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        count, _ = await pipe.execute()
        if count > limit:
            raise HTTPException(status_code=429, detail="Rate limit exceeded. Please try again later.")
    except HTTPException:
        raise
    except Exception:
        pass  # Redis unavailable — skip rate limiting gracefully
