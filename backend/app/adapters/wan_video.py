import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings


class WanVideoAdapter(BaseModelAdapter):
    name = "wan2.2"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        # Wan2.2 14B runs locally via ComfyUI API or custom inference server
        async with httpx.AsyncClient(timeout=600) as client:
            payload = {
                "prompt": request.prompt,
                "image": request.reference_images[0] if request.reference_images else None,
                "num_frames": request.params.get("num_frames", 81),
                "fps": request.params.get("fps", 24),
                "width": request.params.get("width", 864),
                "height": request.params.get("height", 480),
            }
            resp = await client.post(
                f"{settings.wan_video_base_url}/api/generate_video", json=payload
            )
            resp.raise_for_status()
            data = resp.json()
        return GenerateResult(
            file_url=data.get("video_url", ""),
            duration=data.get("duration"),
            metadata=data,
        )
