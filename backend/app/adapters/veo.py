"""
Veo video generation adapter.

Supports two model tiers (tried in order):
  veo-3.0-generate-preview  — latest preview (may require allowlist)
  veo-2.0-generate-001      — GA fallback

API flow (generativelanguage.googleapis.com):
  POST  /v1beta/models/{model}:generateVideo  → LRO name
  GET   /v1beta/{name}                        → poll until done=true
  Files API download                          → re-upload to MinIO for persistence

Auth: google_auth module (service-account Bearer or API key fallback).
"""

import asyncio
import base64
import os
import tempfile

import httpx

from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters._poll import poll_until_done
from app.adapters.google_auth import get_auth_headers
from app.config import get_settings

_BASE = "https://generativelanguage.googleapis.com"

# Try the newest model first; fall back to GA version on 404/403
_VIDEO_MODELS = [
    "veo-3.0-generate-preview",
    "veo-2.0-generate-001",
]


def _make_headers(settings) -> dict[str, str]:
    """Return auth headers: API-key if set, else service-account Bearer."""
    if settings.veo_api_key:
        return {"x-goog-api-key": settings.veo_api_key}
    return get_auth_headers(settings)


async def _download_video(url: str, headers: dict) -> bytes:
    """
    Download a video from the Files API (or any URL).
    Files API URLs require auth; plain CDN URLs work without.
    """
    async with httpx.AsyncClient(timeout=120) as client:
        # Try with auth first (needed for files.googleapis.com URLs)
        resp = await client.get(url, headers=headers)
        if resp.status_code == 401:
            # Public CDN — retry without auth
            resp = await client.get(url)
        resp.raise_for_status()
        return resp.content


async def _try_generate_video(
    prompt: str,
    model: str,
    headers: dict,
    duration: int,
    aspect: str,
    image_b64: str | None,
) -> str:
    """Submit a Veo generation request and poll to completion. Returns raw video URL."""
    body: dict = {
        "model": model,
        "prompt": prompt,
        "generationConfig": {
            "durationSeconds": duration,
            "aspectRatio": aspect,
        },
    }
    if image_b64:
        body["image"] = {"bytesBase64Encoded": image_b64, "mimeType": "image/jpeg"}

    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{_BASE}/v1beta/models/{model}:generateVideo",
            headers={**headers, "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        op = resp.json()

    op_name = op.get("name", "")
    if not op_name:
        raise ValueError(f"Veo did not return an operation name: {op}")

    async def _check() -> tuple[bool, str]:
        async with httpx.AsyncClient(timeout=30) as poll_client:
            r = await poll_client.get(
                f"{_BASE}/v1beta/{op_name}",
                headers=headers,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("done"):
                samples = (
                    data.get("response", {}).get("generatedSamples", [{}])
                )
                uri = (samples[0] if samples else {}).get("video", {}).get("uri", "")
                return True, uri
            return False, ""

    return await poll_until_done(
        _check,
        interval=5.0,
        timeout=600.0,
        label=f"veo:{op_name[-20:]}",
    )


class VeoAdapter(BaseModelAdapter):
    name = "veo"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        from app.utils.storage import upload_file

        settings = get_settings()
        headers = _make_headers(settings)
        p = request.params or {}
        duration = int(p.get("duration", 8))
        aspect = p.get("aspect_ratio", "16:9")

        # Encode reference image to base64 if provided
        image_b64: str | None = None
        if request.reference_images:
            img_ref = request.reference_images[0]
            if img_ref.startswith(("http://", "https://")):
                async with httpx.AsyncClient(timeout=30) as dl:
                    img_resp = await dl.get(img_ref)
                    img_resp.raise_for_status()
                    image_b64 = base64.b64encode(img_resp.content).decode()
            else:
                image_b64 = img_ref  # already base64

        prompt = request.prompt or ""
        video_url = ""
        used_model = ""

        # Try models in preference order
        last_error: Exception | None = None
        for model in _VIDEO_MODELS:
            try:
                video_url = await _try_generate_video(
                    prompt, model, headers, duration, aspect, image_b64
                )
                used_model = model
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (400, 403, 404):
                    last_error = e
                    continue  # try next model
                raise
        else:
            raise RuntimeError(
                f"All Veo models failed. Last error: {last_error}"
            ) from last_error

        if not video_url:
            raise RuntimeError(f"Veo returned empty video URL (model={used_model})")

        # Download video from Files API / GCS and re-upload to MinIO for persistence.
        # Files API URLs expire and require auth — storing them directly would break.
        video_bytes = await _download_video(video_url, headers)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as tmp:
            tmp.write(video_bytes)
            tmp_path = tmp.name
        try:
            file_url = await asyncio.get_running_loop().run_in_executor(
                None, upload_file, tmp_path, "video/mp4"
            )
        finally:
            os.unlink(tmp_path)

        return GenerateResult(
            file_url=file_url,
            metadata={"model": used_model, "original_url": video_url},
        )
