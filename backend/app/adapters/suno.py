import httpx
from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters._poll import poll_until_done
from app.config import get_settings


class SunoAdapter(BaseModelAdapter):
    name = "suno"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        headers = {"Authorization": f"Bearer {settings.suno_api_key}"}

        async with httpx.AsyncClient(timeout=60) as client:
            resp = await client.post(
                "https://api.suno.ai/v1/songs",
                headers=headers,
                json={
                    "prompt": request.prompt,
                    "genre": request.params.get("genre", ""),
                    "lyrics": request.params.get("lyrics", ""),
                },
            )
            resp.raise_for_status()
            data = resp.json()

        song_id = data.get("id", "")
        if not song_id:
            if data.get("audio_url"):
                return GenerateResult(
                    file_url=data["audio_url"],
                    duration=data.get("duration"),
                    metadata=data,
                )
            raise ValueError(f"Suno did not return a song ID: {data}")

        _final: dict = {}

        async with httpx.AsyncClient(timeout=30) as poll_client:
            async def _check() -> tuple[bool, str]:
                r = await poll_client.get(
                    f"https://api.suno.ai/v1/songs/{song_id}", headers=headers
                )
                r.raise_for_status()
                d = r.json()
                status = d.get("status", "")
                if status == "completed":
                    _final.update(d)
                    return True, d.get("audio_url", "")
                if status == "failed":
                    raise RuntimeError(f"Suno generation failed: {d.get('error', 'unknown')}")
                return False, ""

            audio_url = await poll_until_done(_check, interval=5.0, timeout=300.0)
        return GenerateResult(
            file_url=audio_url,
            duration=_final.get("duration"),
            metadata=_final,
        )
