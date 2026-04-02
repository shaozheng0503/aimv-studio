"""Grok Video generation adapter (xAI API).

Grok Video is an async API:
  POST /v1/video/generate         → returns {"task_id": "..."}
  GET  /v1/video/status/{task_id} → poll until status == "completed"
"""

import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters._poll import poll_until_done
from app.config import get_settings

_BASE = "https://api.x.ai"


class GrokVideoAdapter(BaseModelAdapter):
    name = "grok"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        headers = {"Authorization": f"Bearer {settings.grok_video_api_key}"}

        body: dict = {
            "prompt": request.prompt,
            "duration": request.params.get("duration", 6),
            "aspect_ratio": request.params.get("aspect_ratio", "16:9"),
        }
        if request.reference_images:
            body["image_url"] = request.reference_images[0]

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{_BASE}/v1/video/generate",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        task_id = data.get("task_id") or data.get("id", "")
        if not task_id:
            if data.get("video_url"):
                return GenerateResult(file_url=data["video_url"], metadata=data)
            raise ValueError(f"Grok did not return a task_id: {data}")

        async with httpx.AsyncClient(timeout=30) as poll_client:
            async def _check() -> tuple[bool, str]:
                r = await poll_client.get(
                    f"{_BASE}/v1/video/status/{task_id}",
                    headers=headers,
                )
                r.raise_for_status()
                d = r.json()
                status = d.get("status", "")
                if status == "completed":
                    return True, d.get("video_url", "")
                if status in ("failed", "cancelled"):
                    raise RuntimeError(f"Grok Video task {status}: {d.get('error', '')}")
                return False, ""

            video_url = await poll_until_done(_check, interval=4.0, timeout=600.0, label=f"grok:{task_id}")
        return GenerateResult(
            file_url=video_url,
            metadata={"model": "grok-video", "task_id": task_id},
        )
