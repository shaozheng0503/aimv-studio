import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings


class GrokVideoAdapter(BaseModelAdapter):
    name = "grok"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                "https://api.x.ai/v1/video/generate",
                headers={"Authorization": f"Bearer {settings.grok_video_api_key}"},
                json={
                    "prompt": request.prompt,
                    "image_url": request.reference_images[0] if request.reference_images else None,
                    "duration": request.params.get("duration", 6),
                },
            )
            data = resp.json()
        return GenerateResult(file_url=data.get("video_url", ""), metadata=data)
