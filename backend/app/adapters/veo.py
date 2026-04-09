"""
Veo video generation adapter — Vertex AI predictLongRunning.

Confirmed working with service-account auth on project qy-shoplazza-02:
  Model:  veo-2.0-generate-001  (only GA model available for this SA)
  API:    POST .../predictLongRunning  → op_name
  Poll:   POST .../fetchPredictOperation  → response.videos[0].bytesBase64Encoded
  No GCS bucket required — video returned as inline base64.

Duration options (Veo 2.0 hard constraint): 5 / 6 / 7 / 8 seconds
Frontend exposes 5 / 6 / 8 as the three representative choices.

Auth: google_auth module (service-account Bearer).
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

# Only one model confirmed working for this project
_DEFAULT_MODEL = "veo-2.0-generate-001"

# Valid durations for Veo 2.0 text_to_video
# (4s is rejected by the API at generation time; the valid range is 5-8s)
_VALID_DURATIONS = (5, 6, 7, 8)


def _clamp_duration(raw: int) -> int:
    """Round to nearest valid Veo duration (5 / 6 / 7 / 8)."""
    return min(_VALID_DURATIONS, key=lambda d: abs(d - raw))


def _model_base(project_id: str, model: str) -> str:
    return (
        f"{_VERTEX_BASE}/projects/{project_id}"
        f"/locations/us-central1/publishers/google/models/{model}"
    )


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
    Returns raw MP4 bytes decoded from inline base64 in the response.
    """
    base_url = _model_base(project_id, model)
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

    # 1. Start the long-running operation
    async with httpx.AsyncClient(timeout=60) as client:
        resp = await client.post(
            f"{base_url}:predictLongRunning",
            headers={**headers, "Content-Type": "application/json"},
            json=body,
        )
        resp.raise_for_status()
        op_name = resp.json().get("name", "")
    if not op_name:
        raise ValueError(f"Veo: predictLongRunning returned no operation name")

    # 2. Poll until complete via fetchPredictOperation
    poll_body = {"operationName": op_name}
    elapsed = 0.0
    max_wait = 600.0
    interval = 8.0

    while elapsed < max_wait:
        await asyncio.sleep(interval)
        elapsed += interval

        async with httpx.AsyncClient(timeout=30) as poll_client:
            pr = await poll_client.post(
                f"{base_url}:fetchPredictOperation",
                headers={**headers, "Content-Type": "application/json"},
                json=poll_body,
            )
            pr.raise_for_status()
            data = pr.json()

        if not data.get("done"):
            continue

        # Operation finished — check for error or result
        if "error" in data:
            err = data["error"]
            raise RuntimeError(f"Veo generation failed: {err.get('message', err)}")

        videos = data.get("response", {}).get("videos", [])
        if not videos:
            raise RuntimeError(f"Veo returned no videos in response: {data}")

        b64 = videos[0].get("bytesBase64Encoded", "")
        if not b64:
            raise RuntimeError(f"Veo video missing bytesBase64Encoded: {videos[0]}")

        return base64.b64decode(b64)

    raise TimeoutError(f"Veo timed out after {max_wait}s (op={op_name[-20:]})")


class VeoAdapter(BaseModelAdapter):
    """Veo 2.0 via Vertex AI predictLongRunning. Inline base64 response."""
    name = "veo"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        from app.utils.storage import upload_file

        settings = get_settings()
        headers = get_auth_headers(settings)
        _, project_id = get_token_and_project(settings)
        p = request.params or {}

        model = p.get("model", _DEFAULT_MODEL)
        duration = _clamp_duration(int(p.get("duration", 8)))
        aspect = p.get("aspect_ratio", "16:9")

        # Encode reference image to base64 if provided (img2video)
        image_b64: str | None = None
        image_mime: str = "image/jpeg"
        if request.reference_images:
            img_ref = request.reference_images[0]
            if img_ref.startswith(("http://", "https://")):
                async with httpx.AsyncClient(timeout=30) as dl:
                    img_resp = await dl.get(img_ref)
                    img_resp.raise_for_status()
                    raw = img_resp.content
                    image_b64 = base64.b64encode(raw).decode()
            else:
                raw = base64.b64decode(img_ref)
                image_b64 = img_ref  # already base64
            # Detect image format from magic bytes
            if image_b64:
                raw = base64.b64decode(image_b64[:20])
                if raw[:4] == b'\x89PNG':
                    image_mime = "image/png"
                elif raw[:2] == b'\xff\xd8':
                    image_mime = "image/jpeg"
                elif raw[:6] in (b'GIF87a', b'GIF89a'):
                    image_mime = "image/gif"
                elif raw[:4] == b'RIFF':
                    image_mime = "image/webp"

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
            metadata={"model": model, "duration": duration, "aspect": aspect},
        )


# ── Pinned subclasses (currently all use the same GA model) ──────────────────

class Veo31Adapter(VeoAdapter):
    """Veo 3.1 alias — uses veo-2.0-generate-001 (only available model)."""
    name = "veo-3.1"


class Veo30Adapter(VeoAdapter):
    """Veo 3.0 alias — uses veo-2.0-generate-001 (only available model)."""
    name = "veo-3.0"


class Veo20Adapter(VeoAdapter):
    """Veo 2.0 GA — explicit pin to veo-2.0-generate-001."""
    name = "veo-2.0"
