import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings


class SeedanceAdapter(BaseModelAdapter):
    name = "seedance"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                "https://api.seedance.com/v1/generate",
                headers={"Authorization": f"Bearer {settings.seedance_api_key}"},
                json={
                    "prompt": request.prompt,
                    "first_frame_image": request.reference_images[0] if request.reference_images else None,
                    "duration": request.params.get("duration", 5),
                    "aspect_ratio": request.params.get("aspect_ratio", "16:9"),
                },
            )
            data = resp.json()
        # TODO: poll for completion
        return GenerateResult(file_url=data.get("video_url", ""), metadata=data)
