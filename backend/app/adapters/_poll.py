"""Shared async polling utility for video generation APIs.

All cloud video APIs (Veo, Seedance, Grok) are async — they accept a request,
return a job/operation ID, and require polling until the video is ready.
This module provides a single reusable polling loop.
"""

import asyncio
import logging
from typing import Callable, Awaitable

logger = logging.getLogger(__name__)

# Log a heartbeat every N seconds so Celery logs show the task is still alive.
_LOG_INTERVAL = 30.0


async def poll_until_done(
    check_fn: Callable[[], Awaitable[tuple[bool, str]]],
    interval: float = 3.0,
    timeout: float = 600.0,
    label: str = "",
) -> str:
    """Poll check_fn until it signals completion.

    check_fn must return (done: bool, result_url: str).
    Raises TimeoutError if timeout is exceeded.
    Raises RuntimeError if check_fn raises for more than 5 consecutive calls.

    label: optional context string included in log messages (e.g. "veo:op_abc123").
    """
    elapsed = 0.0
    errors = 0
    last_log = 0.0
    tag = f"[{label}] " if label else ""

    while elapsed < timeout:
        try:
            done, url = await check_fn()
            errors = 0
        except Exception as e:
            errors += 1
            logger.warning("%spolling error %d/5: %s", tag, errors, e)
            if errors >= 5:
                raise RuntimeError(f"{tag}Polling failed after 5 consecutive errors: {e}") from e
        else:
            if done:
                if not url:
                    raise RuntimeError(f"{tag}API reported completion but returned no output URL")
                logger.info("%scompleted after %.0fs", tag, elapsed)
                return url

        await asyncio.sleep(interval)
        elapsed += interval

        # Periodic heartbeat log so Celery stdout stays alive
        if elapsed - last_log >= _LOG_INTERVAL:
            remaining = timeout - elapsed
            logger.info("%swaiting… %.0fs elapsed, %.0fs remaining", tag, elapsed, remaining)
            last_log = elapsed

    raise TimeoutError(f"{tag}Generation timed out after {timeout}s")
