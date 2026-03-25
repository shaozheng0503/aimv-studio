import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings


class ZImageAdapter(BaseModelAdapter):
    name = "z-image"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{settings.z_image_base_url}/generate",
                headers={"Authorization": f"Bearer {settings.z_image_api_key}"},
                json={
                    "prompt": request.prompt,
                    "negative_prompt": request.params.get("negative_prompt", ""),
                    "width": request.params.get("width", 1024),
                    "height": request.params.get("height", 1024),
                    "steps": request.params.get("steps", 30),
                    "cfg_scale": request.params.get("cfg_scale", 7.0),
                },
            )
            resp.raise_for_status()
            data = resp.json()
        image_url = data.get("image_url", "")
        if not image_url:
            raise RuntimeError(f"Z-Image returned no image_url: {data}")
        return GenerateResult(file_url=image_url)
