import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings


class SunoAdapter(BaseModelAdapter):
    name = "suno"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        async with httpx.AsyncClient(timeout=300) as client:
            # Submit generation
            resp = await client.post(
                "https://api.suno.ai/v1/songs",
                headers={"Authorization": f"Bearer {settings.suno_api_key}"},
                json={
                    "prompt": request.prompt,
                    "genre": request.params.get("genre", ""),
                    "lyrics": request.params.get("lyrics", ""),
                },
            )
            data = resp.json()
            song_id = data.get("id", "")

            # Poll for completion
            import asyncio
            for _ in range(60):
                status_resp = await client.get(
                    f"https://api.suno.ai/v1/songs/{song_id}",
                    headers={"Authorization": f"Bearer {settings.suno_api_key}"},
                )
                status_data = status_resp.json()
                if status_data.get("status") == "completed":
                    return GenerateResult(
                        file_url=status_data.get("audio_url", ""),
                        duration=status_data.get("duration"),
                        metadata=status_data,
                    )
                await asyncio.sleep(5)

        raise TimeoutError("Suno generation timed out")
