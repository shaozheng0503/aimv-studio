from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult


class WanVideoAdapter(BaseModelAdapter):
    name = "wan2.2"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        # Wan2.2 14B runs locally via ComfyUI API or custom inference server
        import httpx
        async with httpx.AsyncClient(timeout=600) as client:
            payload = {
                "prompt": request.prompt,
                "image": request.reference_images[0] if request.reference_images else None,
                "num_frames": request.params.get("num_frames", 81),
                "fps": request.params.get("fps", 24),
                "width": request.params.get("width", 864),
                "height": request.params.get("height", 480),
            }
            resp = await client.post("http://localhost:8188/api/generate_video", json=payload)
            data = resp.json()
        return GenerateResult(
            file_url=data.get("video_url", ""),
            duration=data.get("duration"),
            metadata=data,
        )
