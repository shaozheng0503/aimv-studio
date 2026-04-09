"""
Shared Google Cloud authentication helper for all Google adapters.

Supports two credential sources (in priority order):
  1. GOOGLE_SA_JSON env-var / settings.google_sa_json  — inline JSON string
  2. settings.google_sa_path                           — path to SA JSON file

Token is cached in-process and refreshed automatically 60s before expiry.
"""

import json
import os
import tempfile
import time

_SCOPES = [
    "https://www.googleapis.com/auth/cloud-platform",
    "https://www.googleapis.com/auth/generative-language",
]

# In-process token cache: {token, expiry_ts, project_id}
_cache: dict = {}
# Temp file path written from inline JSON (reused across calls)
_tmp_sa_path: str = ""


def _ensure_sa_file(settings) -> str:
    """Return a filesystem path to the SA JSON, writing a temp file if needed."""
    global _tmp_sa_path

    # 1. Inline JSON string takes priority
    sa_json = getattr(settings, "google_sa_json", "") or os.environ.get("GOOGLE_SA_JSON", "")
    if sa_json:
        if not _tmp_sa_path or not os.path.exists(_tmp_sa_path):
            tmp = tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False, prefix="gcp_sa_"
            )
            tmp.write(sa_json)
            tmp.flush()
            tmp.close()
            _tmp_sa_path = tmp.name
        return _tmp_sa_path

    # 2. File path
    path = getattr(settings, "google_sa_path", ".credentials/gcp-sa.json")
    if path and os.path.exists(path):
        return path

    raise RuntimeError(
        "Google SA credentials not configured. "
        "Set GOOGLE_SA_JSON env-var or place the SA file at "
        f"{path!r} (currently missing)."
    )


def get_token_and_project(settings) -> tuple[str, str]:
    """Return (access_token, project_id), refreshing from cache when needed."""
    now = time.time()
    if _cache.get("token") and _cache.get("expiry", 0) > now + 60:
        return _cache["token"], _cache["project_id"]

    sa_path = _ensure_sa_file(settings)

    from google.auth.transport.requests import Request
    from google.oauth2.service_account import Credentials

    creds = Credentials.from_service_account_file(sa_path, scopes=_SCOPES)
    creds.refresh(Request())

    with open(sa_path) as f:
        project_id = json.load(f).get("project_id", "unknown")

    _cache.update(
        token=creds.token,
        expiry=creds.expiry.timestamp() if creds.expiry else now + 3600,
        project_id=project_id,
    )
    return _cache["token"], _cache["project_id"]


def get_auth_headers(settings) -> dict[str, str]:
    """Return {"Authorization": "Bearer <token>"} dict ready for HTTP requests."""
    token, _ = get_token_and_project(settings)
    return {"Authorization": f"Bearer {token}"}
