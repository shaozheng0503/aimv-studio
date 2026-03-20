import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings


class VeoAdapter(BaseModelAdapter):
    name = "veo"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/veo-3.1:generateVideo",
                headers={"x-goog-api-key": settings.veo_api_key},
                json={
                    "prompt": request.prompt,
                    "image": request.reference_images[0] if request.reference_images else None,
                    "config": {
                        "duration_seconds": request.params.get("duration", 8),
                        "aspect_ratio": request.params.get("aspect_ratio", "16:9"),
                    },
                },
            )
            data = resp.json()
        return GenerateResult(file_url=data.get("video_url", ""), metadata=data)
