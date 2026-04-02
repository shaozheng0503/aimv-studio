"""Veo 3.1 video generation adapter (Google Generative Language API).

Veo is an async API:
  POST /v1beta/models/veo-3.1:generateVideo  → returns operation name
  GET  /v1beta/{operation_name}              → poll until done=true
"""

import base64
import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters._poll import poll_until_done
from app.config import get_settings

_BASE = "https://generativelanguage.googleapis.com"


class VeoAdapter(BaseModelAdapter):
    name = "veo"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        if settings.veo_api_key:
            headers = {"x-goog-api-key": settings.veo_api_key}
        elif settings.google_sa_path:
            from app.adapters.google_image import _get_access_token
            token, _ = _get_access_token(settings.google_sa_path)
            headers = {"Authorization": f"Bearer {token}"}
        else:
            raise RuntimeError("Veo requires veo_api_key or google_sa_path to be configured")

        body: dict = {
            "model": "veo-3.1",
            "prompt": request.prompt,
            "generationConfig": {
                "durationSeconds": request.params.get("duration", 8),
                "aspectRatio": request.params.get("aspect_ratio", "16:9"),
            },
        }
        if request.reference_images:
            img_ref = request.reference_images[0]
            if img_ref.startswith(("http://", "https://")):
                # Veo API requires base64-encoded bytes, not a URL — download first
                async with httpx.AsyncClient(timeout=30) as dl:
                    img_resp = await dl.get(img_ref)
                    img_resp.raise_for_status()
                    img_b64 = base64.b64encode(img_resp.content).decode()
            else:
                img_b64 = img_ref  # already base64
            body["image"] = {"bytesBase64Encoded": img_b64, "mimeType": "image/jpeg"}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{_BASE}/v1beta/models/veo-3.1:generateVideo",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            op = resp.json()

        op_name = op.get("name", "")
        if not op_name:
            raise ValueError(f"Veo did not return an operation name: {op}")

        async with httpx.AsyncClient(timeout=30) as poll_client:
            async def _check() -> tuple[bool, str]:
                r = await poll_client.get(f"{_BASE}/v1beta/{op_name}", headers=headers)
                r.raise_for_status()
                data = r.json()
                if data.get("done"):
                    videos = (
                        data.get("response", {})
                        .get("generatedSamples", [{}])
                    )
                    video_url = (videos[0] if videos else {}).get("video", {}).get("uri", "")
                    return True, video_url
                return False, ""

            video_url = await poll_until_done(_check, interval=4.0, timeout=600.0, label=f"veo:{op_name[-20:]}")
        return GenerateResult(
            file_url=video_url,
            metadata={"model": "veo-3.1", "operation": op_name},
        )
