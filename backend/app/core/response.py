"""Unified response helpers for raw-dict endpoints.

Pydantic response_model= endpoints skip these — they're only for endpoints
that return plain dicts. This gives all ad-hoc responses a consistent shape:

    {"ok": True,  "data": ..., "message": "..."}
    {"ok": False, "error": "...", "detail": "..."}
"""

from typing import Any


def ok(data: Any = None, message: str = "ok") -> dict:
    """Standard success envelope."""
    return {"ok": True, "data": data, "message": message}


def err(error: str, detail: str | None = None) -> dict:
    """Standard error envelope (for non-HTTPException cases)."""
    return {"ok": False, "error": error, "detail": detail or error}
