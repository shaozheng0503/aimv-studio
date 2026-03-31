"""Shared async polling utility for video generation APIs.

All cloud video APIs (Veo, Seedance, Grok) are async — they accept a request,
return a job/operation ID, and require polling until the video is ready.
This module provides a single reusable polling loop.
"""

import asyncio
import httpx
from typing import Callable, Awaitable


async def poll_until_done(
    check_fn: Callable[[], Awaitable[tuple[bool, str]]],
    interval: float = 3.0,
    timeout: float = 600.0,
) -> str:
    """Poll check_fn until it signals completion.

    check_fn must return (done: bool, video_url: str).
    Raises TimeoutError if timeout is exceeded.
    Raises RuntimeError if check_fn raises for more than 5 consecutive calls.
    """
    elapsed = 0.0
    errors = 0
    while elapsed < timeout:
        try:
            done, url = await check_fn()
            errors = 0
            if done:
                if not url:
                    raise RuntimeError("API reported completion but returned no output URL")
                return url
        except Exception as e:
            errors += 1
            if errors >= 5:
                raise RuntimeError(f"Polling failed after 5 consecutive errors: {e}") from e

        await asyncio.sleep(interval)
        elapsed += interval

    raise TimeoutError(f"Video generation timed out after {timeout}s")
