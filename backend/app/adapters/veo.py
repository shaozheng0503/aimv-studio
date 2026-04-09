"""
Veo video generation adapter — Vertex AI predictLongRunning.

Confirmed available models for project qy-shoplazza-02:
  veo-3.1-generate-001       Veo 3.1 standard  — 4 / 6 / 8 s
  veo-3.1-fast-generate-001  Veo 3.1 Fast      — 4 / 6 / 8 s  (lower latency)
  veo-3.0-generate-001       Veo 3.0           — 4 / 6 / 8 s
  veo-2.0-generate-001       Veo 2.0 GA        — 5 / 6 / 7 / 8 s

API: POST .../predictLongRunning → op_name
Poll: POST .../fetchPredictOperation → response.videos[0].bytesBase64Encoded
No GCS required — video returned inline as base64.
"""

import asyncio
import base64
import os
import tempfile

import httpx

from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters.google_auth import get_auth_headers, get_token_and_project
from app.config import get_settings

_VERTEX_BASE = "https://us-central1-aiplatform.googleapis.com/v1"

# All confirmed-working Veo models (newest/best first)
_MODEL_CATALOG: dict[str, dict] = {
    "veo-3.1-generate-001": {
        "label": "Veo 3.1",
        "valid_durations": (4, 6, 8),
        "default_duration": 8,
    },
    "veo-3.1-fast-generate-001": {
        "label": "Veo 3.1 Fast",
        "valid_durations": (4, 6, 8),
        "default_duration": 6,
    },
    "veo-3.0-generate-001": {
        "label": "Veo 3.0",
        "valid_durations": (4, 6, 8),
        "default_duration": 8,
    },
    "veo-2.0-generate-001": {
        "label": "Veo 2.0 GA",
        "valid_durations": (5, 6, 7, 8),
        "default_duration": 8,
    },
}

# Default cascade: newest → oldest
_DEFAULT_CASCADE = list(_MODEL_CATALOG.keys())
# Primary default (what "auto" resolves to)
_DEFAULT_MODEL = "veo-3.1-generate-001"


def _clamp_duration(raw: int, model: str) -> int:
    """Round to the nearest valid duration for the given model."""
    valid = _MODEL_CATALOG.get(model, {}).get("valid_durations", (4, 6, 8))
    return min(valid, key=lambda d: abs(d - raw))


def _model_url(project_id: str, model: str, method: str) -> str:
    return (
        f"{_VERTEX_BASE}/projects/{project_id}"
        f"/locations/us-central1/publishers/google/models/{model}:{method}"
    )


def _detect_mime(b64_prefix: str) -> str:
    """Detect image MIME type from the first few base64-decoded bytes."""
    try:
        raw = base64.b64decode(b64_prefix[:20] + "==")
    except Exception:
        return "image/jpeg"
    if raw[:4] == b"\x89PNG":
        return "image/png"
    if raw[:2] == b"\xff\xd8":
        return "image/jpeg"
    if raw[:6] in (b"GIF87a", b"GIF89a"):
        return "image/gif"
    if raw[:4] == b"RIFF":
        return "image/webp"
    return "image/jpeg"


async def _generate(
    prompt: str,
    model: str,
    headers: dict,
    project_id: str,
    duration: int,
    aspect: str,
    image_b64: str | None,
    image_mime: str = "image/jpeg",
) -> bytes:
    """
    Submit a Veo generation request and poll to completion.
    Returns raw MP4 bytes from the inline base64 response.
    """
    instance: dict = {"prompt": prompt}
    if image_b64:
        instance["image"] = {"bytesBase64Encoded": image_b64, "mimeType": image_mime}

    body = {
        "instances": [instance],
        "parameters": {
            "durationSeconds": duration,
            "aspectRatio": aspect,
            "numberOfVideos": 1,
        },
    }

    # 1. Submit
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            _model_url(project_id, model, "predictLongRunning"),
            headers={**headers, "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        op_name = resp.json().get("name", "")
    if not op_name:
        raise ValueError(f"Veo: no operation name returned by {model}")

    # 2. Poll via fetchPredictOperation
    poll_body = {"operationName": op_name}
    elapsed = 0.0
    max_wait = 600.0
    interval = 8.0

    while elapsed < max_wait:
        await asyncio.sleep(interval)
        elapsed += interval

        async with httpx.AsyncClient(timeout=30) as poll_client:
            pr = await poll_client.post(
                _model_url(project_id, model, "fetchPredictOperation"),
                headers={**headers, "Content-Type": "application/json"},
                json=poll_body,
            )
            pr.raise_for_status()
            data = pr.json()

        if not data.get("done"):
            continue

        if "error" in data:
            raise RuntimeError(f"Veo [{model}] generation failed: {data['error'].get('message', data['error'])}")

        response = data.get("response", {})
        videos = response.get("videos", [])
        if not videos:
            # Check for RAI / safety filter rejection
            rai_count = response.get("raiMediaFilteredCount", 0)
            rai_reasons = response.get("raiMediaFilteredReasons", [])
            if rai_count or rai_reasons:
                reason = rai_reasons[0] if rai_reasons else "content policy"
                raise RuntimeError(
                    f"Veo [{model}] content filtered by safety policy — "
                    f"try rephrasing the prompt. Detail: {reason[:120]}"
                )
            raise RuntimeError(f"Veo [{model}] returned no videos: {data}")

        b64 = videos[0].get("bytesBase64Encoded", "")
        if not b64:
            raise RuntimeError(f"Veo [{model}] missing bytesBase64Encoded: {videos[0]}")

        return base64.b64decode(b64)

    raise TimeoutError(f"Veo [{model}] timed out after {max_wait}s (op={op_name[-24:]})")


class VeoAdapter(BaseModelAdapter):
    """
    Veo adapter with model cascade.
    Default: veo-3.1-generate-001 → veo-3.0-generate-001 → veo-2.0-generate-001
    """
    name = "veo"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        from app.utils.storage import upload_file

        settings = get_settings()
        headers = get_auth_headers(settings)
        _, project_id = get_token_and_project(settings)
        p = request.params or {}

        # Which model(s) to try
        requested = p.get("model", "")
        cascade = [requested] if requested else _DEFAULT_CASCADE

        # Parse common params (will be re-clamped per model in loop)
        raw_dur = int(p.get("duration", 8))
        aspect = p.get("aspect_ratio", "16:9")

        # Encode reference image (img2video)
        image_b64: str | None = None
        image_mime: str = "image/jpeg"
        if request.reference_images:
            img_ref = request.reference_images[0]
            if img_ref.startswith(("http://", "https://")):
                async with httpx.AsyncClient(timeout=30) as dl:
                    img_resp = await dl.get(img_ref)
                    img_resp.raise_for_status()
                    image_b64 = base64.b64encode(img_resp.content).decode()
            else:
                image_b64 = img_ref  # already base64
            if image_b64:
                image_mime = _detect_mime(image_b64)

        # Try each model in cascade order
        video_bytes: bytes | None = None
        used_model = ""
        last_error: Exception | None = None

        for model in cascade:
            duration = _clamp_duration(raw_dur, model)
            try:
                video_bytes = await _generate(
                    prompt=request.prompt or "",
                    model=model,
                    headers=headers,
                    project_id=project_id,
                    duration=duration,
                    aspect=aspect,
                    image_b64=image_b64,
                    image_mime=image_mime,
                )
                used_model = model
                break
            except httpx.HTTPStatusError as e:
                if e.response.status_code in (400, 403, 404):
                    last_error = e
                    continue  # try next model
                raise
            except RuntimeError as e:
                # Generation-level error (e.g. unsupported duration) — try next
                last_error = e
                continue
        else:
            raise RuntimeError(
                f"All Veo models in cascade failed. Last: {last_error}"
            ) from last_error

        if not video_bytes:
            raise RuntimeError(f"Empty video bytes from {used_model}")

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
            metadata={"model": used_model, "duration": duration, "aspect": aspect},
        )


# ── Pinned per-model subclasses ───────────────────────────────────────────────

class Veo31Adapter(VeoAdapter):
    """Veo 3.1 standard — pin to veo-3.1-generate-001."""
    name = "veo-3.1"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        return await super().generate(GenerateRequest(
            prompt=request.prompt,
            params={**(request.params or {}), "model": "veo-3.1-generate-001"},
            reference_images=request.reference_images,
        ))


class Veo31FastAdapter(VeoAdapter):
    """Veo 3.1 Fast — pin to veo-3.1-fast-generate-001 (lower latency)."""
    name = "veo-3.1-fast"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        return await super().generate(GenerateRequest(
            prompt=request.prompt,
            params={**(request.params or {}), "model": "veo-3.1-fast-generate-001"},
            reference_images=request.reference_images,
        ))


class Veo30Adapter(VeoAdapter):
    """Veo 3.0 — pin to veo-3.0-generate-001."""
    name = "veo-3.0"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        return await super().generate(GenerateRequest(
            prompt=request.prompt,
            params={**(request.params or {}), "model": "veo-3.0-generate-001"},
            reference_images=request.reference_images,
        ))


class Veo20Adapter(VeoAdapter):
    """Veo 2.0 GA — pin to veo-2.0-generate-001."""
    name = "veo-2.0"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        return await super().generate(GenerateRequest(
            prompt=request.prompt,
            params={**(request.params or {}), "model": "veo-2.0-generate-001"},
            reference_images=request.reference_images,
        ))
