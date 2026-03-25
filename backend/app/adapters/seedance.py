"""Seedance 2.0 video generation adapter.

Seedance is an async API:
  POST /v1/generate    → returns {"task_id": "..."}
  GET  /v1/task/{id}   → poll until status == "completed"
"""

import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters._poll import poll_until_done
from app.config import get_settings

_BASE = "https://api.seedance.com"


class SeedanceAdapter(BaseModelAdapter):
    name = "seedance"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        headers = {"Authorization": f"Bearer {settings.seedance_api_key}"}

        body: dict = {
            "prompt": request.prompt,
            "duration": request.params.get("duration", 5),
            "aspect_ratio": request.params.get("aspect_ratio", "16:9"),
        }
        if request.reference_images:
            body["first_frame_image"] = request.reference_images[0]

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                f"{_BASE}/v1/generate",
                headers=headers,
                json=body,
            )
            resp.raise_for_status()
            data = resp.json()

        task_id = data.get("task_id") or data.get("id", "")
        if not task_id:
            # Some Seedance endpoints return video_url directly (synchronous mode)
            if data.get("video_url"):
                return GenerateResult(file_url=data["video_url"], metadata=data)
            raise ValueError(f"Seedance did not return a task_id: {data}")

        async with httpx.AsyncClient(timeout=30) as poll_client:
            async def _check() -> tuple[bool, str]:
                r = await poll_client.get(f"{_BASE}/v1/task/{task_id}", headers=headers)
                r.raise_for_status()
                d = r.json()
                status = d.get("status", "")
                if status == "completed":
                    return True, d.get("video_url", "")
                if status == "failed":
                    raise RuntimeError(f"Seedance task failed: {d.get('error', 'unknown')}")
                return False, ""

            video_url = await poll_until_done(_check, interval=3.0, timeout=600.0)
        return GenerateResult(
            file_url=video_url,
            metadata={"model": "seedance-2.0", "task_id": task_id},
        )
