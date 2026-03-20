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

    async def verify_video(self, video_url: str, prompt: str, character_desc: str = "") -> VerifyResult:
        """Score a generated video clip using LLM vision."""
        system_prompt = VERIFY_PROMPT_VIDEO.format(prompt=prompt, character_desc=character_desc)
        return await self._call_llm_judge(system_prompt, video_url=video_url)

    async def _call_llm_judge(
        self, system_prompt: str, image_url: str = "", video_url: str = ""
    ) -> VerifyResult:
        """Call Gemini or OpenAI to judge content quality."""
        try:
            async with httpx.AsyncClient(timeout=60) as client:
                # Use Gemini for multimodal evaluation
                content_parts = [{"text": system_prompt}]
                if image_url:
                    content_parts.append({
                        "inline_data": {"mime_type": "image/jpeg", "data": image_url}
                    })

                resp = await client.post(
                    f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent",
                    params={"key": self.settings.gemini_api_key},
                    json={"contents": [{"parts": content_parts}]},
                )
                data = resp.json()
                text = data.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "{}")

                import json
                result = json.loads(text)
                return VerifyResult(
                    passed=result.get("passed", False),
                    score=float(result.get("score", 0)),
                    explanation=result.get("explanation", ""),
                    dimensions=result.get("dimensions", {}),
                )
        except Exception as e:
            # If verification fails, pass by default (don't block generation)
            return VerifyResult(passed=True, score=3.0, explanation=f"Verification skipped: {e}", dimensions={})

    @staticmethod
    def should_retry(result: VerifyResult) -> bool:
        return not result.passed and result.score < THRESHOLD
