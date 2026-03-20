import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings


class LyriaAdapter(BaseModelAdapter):
    name = "lyria"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        # Google Lyria via Vertex AI / AI Studio API
        async with httpx.AsyncClient(timeout=300) as client:
            resp = await client.post(
                "https://generativelanguage.googleapis.com/v1beta/models/lyria-realtime:generate",
                headers={"x-goog-api-key": settings.lyria_api_key},
                json={
                    "prompt": request.prompt,
                    "config": {
                        "duration_seconds": request.params.get("duration", 30),
                        "style": request.params.get("style", ""),
                    },
                },
            )
            data = resp.json()
        return GenerateResult(
            file_url=data.get("audio_url", ""),
            duration=data.get("duration"),
            metadata=data,
        )
