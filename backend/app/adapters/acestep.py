import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings


class ACEStepAdapter(BaseModelAdapter):
    name = "acestep"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        # ACEStep 1.5 runs locally via REST API (Gradio or custom server)
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                f"{settings.acestep_base_url}/api/generate",
                json={
                    "prompt": request.prompt,
                    "lyrics": request.params.get("lyrics", ""),
                    "genre": request.params.get("genre", "pop"),
                    "bpm": request.params.get("bpm", 120),
                    "duration": request.params.get("duration", 180),
                    **request.params,
                },
            )
            resp.raise_for_status()
            data = resp.json()
        return GenerateResult(
            file_url=data.get("audio_url", ""),
            duration=data.get("duration"),
            metadata=data,
        )
