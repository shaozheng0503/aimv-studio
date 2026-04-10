"""
Google Image Generation adapter.

Supported image models (newest first):
  gemini-2.0-flash-preview-image-generation  — Gemini Flash image gen (fastest)
  imagen-3.0-generate-002                    — Imagen 3.0 via Vertex AI (higher quality)

Auto-cascade: tries Gemini Flash first; on 400/403/404 falls back to Imagen 3.0.
Each model can also be called directly via the pinned adapter subclasses.

Auth: google_auth.get_auth_headers() — handles both file-path and inline JSON SA.
"""

import asyncio
import base64
import os
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters.google_auth import get_auth_headers, get_token_and_project
from app.config import get_settings

# Gemini image generation model (generativelanguage.googleapis.com)
_GEMINI_IMAGE_MODEL = "gemini-2.0-flash-preview-image-generation"

# Imagen models on Vertex AI (us-central1)
_IMAGEN_MODELS = {
    "imagen-3.0": "imagen-3.0-generate-002",   # current GA
    "imagen-3.0-fast": "imagen-3.0-fast-generate-001",  # fast variant
}
_IMAGEN_DEFAULT = _IMAGEN_MODELS["imagen-3.0"]

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


def _call_imagen(
    prompt: str,
    headers: dict,
    project_id: str,
    aspect: str = "16:9",
    model: str = "",
) -> bytes:
    """Call Imagen on Vertex AI. Returns raw PNG bytes."""
    api_model = _IMAGEN_MODELS.get(model, model) if model else _IMAGEN_DEFAULT
    url = (
        f"https://us-central1-aiplatform.googleapis.com/v1/projects/{project_id}"
        f"/locations/us-central1/publishers/google/models/{api_model}:predict"
    )
    last_err: Exception | None = None
    for attempt in range(3):
        try:
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
            if preds and preds[0].get("bytesBase64Encoded"):
                return base64.b64decode(preds[0]["bytesBase64Encoded"])
            # Some transient backend responses can be 200 with empty predictions.
            raise RuntimeError(f"No predictions from Imagen: {data}")
        except httpx.HTTPStatusError as e:
            last_err = e
            # Retry only transient server-side failures.
            if e.response.status_code >= 500 and attempt < 2:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except Exception as e:
            last_err = e
            if attempt < 2:
                time.sleep(1.2 * (attempt + 1))
                continue
            raise
    raise RuntimeError(str(last_err) if last_err else "Imagen request failed")


def _generate_sync(request: GenerateRequest, settings) -> GenerateResult:
    from app.utils.storage import upload_file

    p = request.params or {}
    prompt = p.get("description") or request.prompt or ""
    aspect = p.get("aspect_ratio", "16:9")

    headers = get_auth_headers(settings)
    _, project_id = get_token_and_project(settings)

    img_bytes: bytes | None = None
    model_used = _GEMINI_IMAGE_MODEL

    # Which image backend to use (default: Gemini Flash → Imagen fallback)
    pinned = p.get("image_model", "")

    if pinned.startswith("imagen"):
        # Caller explicitly requested Imagen — skip Gemini
        model_used = _IMAGEN_MODELS.get(pinned, _IMAGEN_DEFAULT)
        img_bytes = _call_imagen(prompt, headers, project_id, aspect, pinned)
    else:
        try:
            img_bytes = _call_gemini_image(prompt, headers, aspect)
        except httpx.HTTPStatusError as e:
            if e.response.status_code in (400, 403, 404):
                # Gemini image gen not enabled on this project → fall back to Imagen 3.0
                model_used = _IMAGEN_DEFAULT
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
    """Auto-cascade: Gemini 2.0 Flash image gen → Imagen 3.0 fallback."""
    name = "gemini-image"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            return await loop.run_in_executor(pool, _generate_sync, request, settings)


class Imagen3Adapter(GeminiImageAdapter):
    """Pin directly to Imagen 3.0 on Vertex AI (skips Gemini Flash)."""
    name = "imagen-3"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        req = GenerateRequest(
            prompt=request.prompt,
            params={**(request.params or {}), "image_model": "imagen-3.0"},
            reference_images=request.reference_images,
        )
        return await super().generate(req)


class Imagen3FastAdapter(GeminiImageAdapter):
    """Pin to Imagen 3.0 Fast (lower latency, slightly lower quality)."""
    name = "imagen-3-fast"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        req = GenerateRequest(
            prompt=request.prompt,
            params={**(request.params or {}), "image_model": "imagen-3.0-fast"},
            reference_images=request.reference_images,
        )
        return await super().generate(req)
