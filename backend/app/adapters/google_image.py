"""
Google Image Generation adapter.

Supports two backends (auto-detected at runtime):
  1. gemini-2.0-flash-preview-image-generation  via generativelanguage.googleapis.com
     — requires Generative Language API enabled in the GCP project
  2. imagen-3.0-generate-002  via Vertex AI (us-central1)
     — fallback, no extra API enablement needed

Auth: Google Cloud service account JSON at settings.google_sa_path
"""
import asyncio
import base64
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings

_GEMINI_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"
_IMAGEN_MODEL = "imagen-3.0-generate-002"
_GENERATIVELANG_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{_GEMINI_IMAGE_MODEL}:generateContent"
)

# Simple token cache: {token, expiry_ts, project_id}
_token_cache: dict = {}


def _get_access_token(sa_path: str) -> tuple[str, str]:
    """Return (access_token, project_id), using cached token when still valid."""
    now = time.time()
    if _token_cache.get("token") and _token_cache.get("expiry", 0) > now + 60:
        return _token_cache["token"], _token_cache["project_id"]

    from google.auth.transport.requests import Request
    from google.oauth2.service_account import Credentials
    creds = Credentials.from_service_account_file(
        sa_path,
        scopes=["https://www.googleapis.com/auth/cloud-platform",
                "https://www.googleapis.com/auth/generative-language"],
    )
    creds.refresh(Request())
    _token_cache.update({
        "token": creds.token,
        "expiry": creds.expiry.timestamp() if creds.expiry else now + 3600,
        "project_id": creds.service_account_email.split("@")[1].split(".")[0]
            if "@" in (creds.service_account_email or "") else "unknown",
    })
    import json
    with open(sa_path) as f:
        _token_cache["project_id"] = json.load(f).get("project_id", "unknown")
    return _token_cache["token"], _token_cache["project_id"]


def _call_gemini_image(prompt: str, token: str, aspect: str = "16:9") -> bytes:
    """Call gemini-2.0-flash-preview-image-generation, return raw image bytes."""
    width, height = {"16:9": (1280, 720), "1:1": (1024, 1024),
                     "9:16": (720, 1280)}.get(aspect, (1280, 720))
    resp = httpx.post(
        _GENERATIVELANG_URL,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {
                "responseModalities": ["IMAGE", "TEXT"],
            },
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    for p in parts:
        if "inlineData" in p:
            return base64.b64decode(p["inlineData"]["data"])
    raise RuntimeError(f"No image in Gemini response: {data}")


def _call_imagen(prompt: str, token: str, project_id: str,
                 aspect: str = "16:9") -> bytes:
    """Call imagen-3.0-generate-002 on Vertex AI, return raw image bytes."""
    url = (f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}"
           "/locations/us-central1/publishers/google/models/"
           f"{_IMAGEN_MODEL}:predict")
    resp = httpx.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": aspect},
        },
        timeout=60,
    )
    resp.raise_for_status()
    data = resp.json()
    preds = data.get("predictions", [])
    if not preds:
        raise RuntimeError(f"No predictions from Imagen: {data}")
    return base64.b64decode(preds[0]["bytesBase64Encoded"])


def _generate_sync(request: GenerateRequest, sa_path: str) -> GenerateResult:
    from app.utils.storage import upload_file

    p = request.params or {}
    prompt = p.get("description") or request.prompt or ""
    aspect = p.get("aspect_ratio", "16:9")

    token, project_id = _get_access_token(sa_path)

    # Try gemini-flash-image first, fall back to imagen-3.0
    img_bytes: bytes | None = None
    model_used = _GEMINI_IMAGE_MODEL
    try:
        img_bytes = _call_gemini_image(prompt, token, aspect)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (403, 404):
            # API not enabled or model not found → fall back to Imagen
            model_used = _IMAGEN_MODEL
            img_bytes = _call_imagen(prompt, token, project_id, aspect)
        else:
            raise

    # Save to temp file and upload to MinIO
    suffix = ".png"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp.write(img_bytes)
        tmp_path = tmp.name
    try:
        file_url = upload_file(tmp_path, "image/png")
    finally:
        os.unlink(tmp_path)

    return GenerateResult(
        file_url=file_url,
        metadata={"model": model_used, "prompt": prompt},
    )


class GeminiImageAdapter(BaseModelAdapter):
    name = "gemini-image"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        sa_path = settings.google_sa_path
        if not sa_path or not os.path.exists(sa_path):
            raise RuntimeError(f"google_sa_path not configured or file missing: {sa_path!r}")

        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = await loop.run_in_executor(pool, _generate_sync, request, sa_path)
        return result
