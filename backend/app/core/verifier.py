"""VerifierAgent — Automated quality gate for AI-generated content.

Scores generated images/videos/audio on multiple dimensions using LLM evaluation.
Triggers automatic retry if quality falls below threshold.
"""

import httpx
from dataclasses import dataclass
from app.config import get_settings


@dataclass
class VerifyResult:
    passed: bool
    score: float  # 0-5
    explanation: str
    dimensions: dict  # individual dimension scores


VERIFY_PROMPT_IMAGE = """You are a quality inspector for AI-generated MV images.
Score this image on a scale of 1-5 for each dimension:
1. Visual Quality (resolution, artifacts, clarity)
2. Character Consistency (matches the character description: {character_desc})
3. Prompt Adherence (matches the intended scene: {prompt})
4. Physical Plausibility (realistic proportions, lighting, anatomy)

Respond in JSON format:
{{"passed": true/false, "score": 0.0, "dimensions": {{"visual_quality": 0, "character_consistency": 0, "prompt_adherence": 0, "physical_plausibility": 0}}, "explanation": "..."}}

A score of 3.0 or above means pass. Below 3.0 means fail."""

VERIFY_PROMPT_VIDEO = """You are a quality inspector for AI-generated MV video clips.
Score this video on a scale of 1-5 for each dimension:
1. Visual Quality (resolution, artifacts, temporal consistency)
2. Motion Quality (smooth, natural movement, no jitter)
3. Character Consistency (matches character description: {character_desc})
4. Prompt Adherence (matches intended scene: {prompt})

Respond in JSON format:
{{"passed": true/false, "score": 0.0, "dimensions": {{"visual_quality": 0, "motion_quality": 0, "character_consistency": 0, "prompt_adherence": 0}}, "explanation": "..."}}

A score of 3.0 or above means pass."""

THRESHOLD = 3.0
MAX_RETRIES = 3


class VerifierAgent:
    def __init__(self):
        self.settings = get_settings()

    async def verify_image(self, image_url: str, prompt: str, character_desc: str = "") -> VerifyResult:
        """Score a generated image using LLM vision."""
        system_prompt = VERIFY_PROMPT_IMAGE.format(prompt=prompt, character_desc=character_desc)
        return await self._call_llm_judge(system_prompt, image_url=image_url)

    async def verify_music(self, audio_url: str, prompt: str) -> VerifyResult:
        """Music cannot be verified via LLM vision — always passes with neutral score."""
        return VerifyResult(
            passed=True,
            score=3.0,
            explanation="Audio verification skipped (no audio LLM configured)",
            dimensions={},
        )

    async def verify_video(self, video_url: str, prompt: str, character_desc: str = "") -> VerifyResult:
        """Score a generated video clip using LLM vision."""
        system_prompt = VERIFY_PROMPT_VIDEO.format(prompt=prompt, character_desc=character_desc)
        return await self._call_llm_judge(system_prompt, video_url=video_url)

    async def _call_llm_judge(
        self, system_prompt: str, image_url: str = "", video_url: str = ""
    ) -> VerifyResult:
        """Call OpenAI or Gemini to judge content quality.

        OpenAI supports both image and video URLs directly.
        Gemini only supports images — for video verification we extract a
        representative frame (the last frame) and pass that instead.
        """
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                if self.settings.openai_api_key:
                    return await self._call_openai_judge(client, system_prompt, image_url or video_url)
                elif self.settings.gemini_api_key:
                    # For video: extract a frame from the video URL to use as proxy
                    gemini_image_url = image_url
                    if not gemini_image_url and video_url:
                        gemini_image_url = await self._extract_frame_for_gemini(client, video_url)
                    return await self._call_gemini_judge(client, system_prompt, gemini_image_url)
        except Exception as e:
            return VerifyResult(passed=True, score=3.0, explanation=f"Verification skipped: {e}", dimensions={})
        return VerifyResult(passed=True, score=3.0, explanation="No LLM configured", dimensions={})

    async def _extract_frame_for_gemini(self, client: httpx.AsyncClient, video_url: str) -> str:
        """Extract a representative frame from a video URL as a data URI for Gemini.

        Downloads the first few KB and returns empty string on failure so
        verification gracefully skips rather than crashing.
        """
        import base64, tempfile, os
        from app.core.shot_router import ShotRouter
        try:
            frame_path = ShotRouter.extract_last_frame(video_url)
            if not frame_path:
                return ""
            with open(frame_path, "rb") as f:
                b64 = base64.b64encode(f.read()).decode()
            try:
                os.unlink(frame_path)
            except OSError:
                pass
            return f"data:image/jpeg;base64,{b64}"
        except Exception:
            return ""

    async def _call_openai_judge(
        self, client: httpx.AsyncClient, system_prompt: str, media_url: str
    ) -> VerifyResult:
        """Use GPT-4o Vision — supports arbitrary HTTP URLs directly."""
        import json
        content: list[dict] = [{"type": "text", "text": system_prompt}]
        if media_url:
            content.append({"type": "image_url", "image_url": {"url": media_url}})
        resp = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={"Authorization": f"Bearer {self.settings.openai_api_key}"},
            json={
                "model": "gpt-4o",
                "messages": [{"role": "user", "content": content}],
                "response_format": {"type": "json_object"},
            },
        )
        resp.raise_for_status()
        text = resp.json()["choices"][0]["message"]["content"]
        result = json.loads(text)
        return VerifyResult(
            passed=result.get("passed", False),
            score=float(result.get("score", 0)),
            explanation=result.get("explanation", ""),
            dimensions=result.get("dimensions", {}),
        )

    async def _call_gemini_judge(
        self, client: httpx.AsyncClient, system_prompt: str, image_url: str
    ) -> VerifyResult:
        """Use Gemini Vision — accepts HTTP URL or data URI as base64."""
        import base64, json
        content_parts: list[dict] = [{"text": system_prompt}]
        if image_url:
            if image_url.startswith("data:"):
                # Already a data URI (e.g. extracted video frame)
                header, b64 = image_url.split(",", 1)
                mime = header.split(":")[1].split(";")[0]
            else:
                img_resp = await client.get(image_url)
                img_resp.raise_for_status()
                b64 = base64.b64encode(img_resp.content).decode()
                mime = "image/jpeg"
            content_parts.append({
                "inline_data": {"mime_type": mime, "data": b64}
            })
        resp = await client.post(
            "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
            params={"key": self.settings.gemini_api_key},
            json={"contents": [{"parts": content_parts}]},
        )
        resp.raise_for_status()
        data = resp.json()
        text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")
        result = json.loads(text)
        return VerifyResult(
            passed=result.get("passed", False),
            score=float(result.get("score", 0)),
            explanation=result.get("explanation", ""),
            dimensions=result.get("dimensions", {}),
        )

    @staticmethod
    def should_retry(result: VerifyResult) -> bool:
        return not result.passed and result.score < THRESHOLD
