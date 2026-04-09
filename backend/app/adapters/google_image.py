"""
Google Image Generation adapter.

Tries two backends in order:
  1. Gemini 2.0 Flash  (generativelanguage.googleapis.com)
     — fastest, free tier available, returns inline base64
  2. Imagen 3.0        (Vertex AI, us-central1)
     — fallback when Gemini image gen is not enabled on the project

Auth: google_auth.get_auth_headers() — handles both file-path and inline JSON SA.
"""

import asyncio
import base64
import os
import tempfile
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters.google_auth import get_auth_headers, get_token_and_project
from app.config import get_settings

_GEMINI_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"
_IMAGEN_MODEL = "imagen-3.0-generate-002"

_GEMINI_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    f"{_GEMINI_IMAGE_MODEL}:generateContent"
)


def _call_gemini_image(prompt: str, headers: dict, aspect: str = "16:9") -> bytes:
    """Call Gemini 2.0 Flash image generation. Returns raw PNG bytes."""
    resp = httpx.post(
        _GEMINI_URL,
        headers={**headers, "Content-Type": "application/json"},
        json={
            "contents": [{"parts": [{"text": prompt}]}],
            "generationConfig": {"responseModalities": ["IMAGE", "TEXT"]},
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    parts = data.get("candidates", [{}])[0].get("content", {}).get("parts", [])
    for part in parts:
        if "inlineData" in part:
            return base64.b64decode(part["inlineData"]["data"])
    raise RuntimeError(f"No image in Gemini response: {data}")


def _call_imagen(prompt: str, headers: dict, project_id: str, aspect: str = "16:9") -> bytes:
    """Call Imagen 3.0 on Vertex AI. Returns raw PNG bytes."""
    url = (
        f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}"
        "/locations/us-central1/publishers/google/models/"
        f"{_IMAGEN_MODEL}:predict"
    )
    resp = httpx.post(
        url,
        headers={**headers, "Content-Type": "application/json"},
        json={
            "instances": [{"prompt": prompt}],
            "parameters": {"sampleCount": 1, "aspectRatio": aspect},
        },
        timeout=90,
    )
    resp.raise_for_status()
    data = resp.json()
    preds = data.get("predictions", [])
    if not preds:
        raise RuntimeError(f"No predictions from Imagen: {data}")
    return base64.b64decode(preds[0]["bytesBase64Encoded"])


def _generate_sync(request: GenerateRequest, settings) -> GenerateResult:
    from app.utils.storage import upload_file

    p = request.params or {}
    prompt = p.get("description") or request.prompt or ""
    aspect = p.get("aspect_ratio", "16:9")

    headers = get_auth_headers(settings)
    _, project_id = get_token_and_project(settings)

    img_bytes: bytes | None = None
    model_used = _GEMINI_IMAGE_MODEL

    try:
        img_bytes = _call_gemini_image(prompt, headers, aspect)
    except httpx.HTTPStatusError as e:
        if e.response.status_code in (400, 403, 404):
            # API not enabled or model unavailable → fallback to Imagen 3.0
            model_used = _IMAGEN_MODEL
            img_bytes = _call_imagen(prompt, headers, project_id, aspect)
        else:
            raise

    with tempfile.NamedTemporaryFile(delete=False, suffix=".png") as tmp:
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
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, _generate_sync, request, settings)
