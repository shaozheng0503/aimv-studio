"""GenerationService — Dispatches generation tasks to model adapters.

Handles the full generate → verify → retry loop for each asset type.
Uses CharacterBank for prompt enrichment and VerifierAgent for quality gates.
"""

from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters.z_image import ZImageAdapter
from app.adapters.acestep import ACEStepAdapter
from app.adapters.suno import SunoAdapter
from app.adapters.lyria import LyriaAdapter
from app.adapters.wan_video import WanVideoAdapter
from app.adapters.seedance import SeedanceAdapter
from app.adapters.veo import VeoAdapter
from app.adapters.grok_video import GrokVideoAdapter
from app.adapters.google_image import GeminiImageAdapter
from app.core.character_bank import CharacterBank
from app.core.verifier import VerifierAgent, MAX_RETRIES


ADAPTER_MAP: dict[str, type[BaseModelAdapter]] = {
    "z-image": ZImageAdapter,
    "acestep": ACEStepAdapter,
    "suno": SunoAdapter,
    "lyria": LyriaAdapter,
    "wan2.2": WanVideoAdapter,
    "seedance": SeedanceAdapter,
    "veo": VeoAdapter,
    "grok": GrokVideoAdapter,
    "gemini-image": GeminiImageAdapter,
}

# Maps human-readable / frontend display names → canonical adapter keys.
# Allows the frontend to store display names (e.g. "Veo 3.1") without breaking.
_MODEL_NAME_ALIASES: dict[str, str] = {
    # Space variants (canonical display names lowercased)
    "veo 3.1": "veo",
    "veo3.1": "veo",
    "seedance 2.0": "seedance",
    "seedance2.0": "seedance",
    "wan 2.2": "wan2.2",
    "wan2.2": "wan2.2",
    "kling 2.0": "kling",
    "hailuo 2.0": "hailuo",
    "grok video 1.0": "grok",
    "grok video": "grok",
    # Underscore variants (from frontend toLowerCase().replace(/\s/g,'_') legacy)
    "veo_3.1": "veo",
    "seedance_2.0": "seedance",
    "kling_2.0": "kling",
    "hailuo_2.0": "hailuo",
    "grok_video_1.0": "grok",
    "grok_video": "grok",
    "z_image": "z-image",
    "gemini_image": "gemini-image",
    "gemini image": "gemini-image",
}


def _normalize_model_name(name: str) -> str:
    """Return the canonical adapter key for a (possibly display-form) model name."""
    key = name.strip().lower()
    return _MODEL_NAME_ALIASES.get(key, key)


class GenerationService:

    def __init__(self):
        self.verifier = VerifierAgent()
        self._adapter_instances: dict[str, BaseModelAdapter] = {}

    def get_adapter(self, model_name: str) -> BaseModelAdapter:
        canonical = _normalize_model_name(model_name)
        if canonical not in self._adapter_instances:
            adapter_cls = ADAPTER_MAP.get(canonical)
            if not adapter_cls:
                raise ValueError(f"Unknown model: {model_name!r} (resolved to {canonical!r})")
            self._adapter_instances[canonical] = adapter_cls()
        return self._adapter_instances[canonical]

    async def generate_image(
        self,
        prompt: str,
        model_name: str = "z-image",
        character_bank: CharacterBank | None = None,
        character_name: str = "",
        params: dict | None = None,
        reference_images: list[str] | None = None,
    ) -> GenerateResult:
        """Generate an image with character enrichment and quality verification."""

        # Enrich prompt with character info
        if character_bank and character_name:
            prompt = character_bank.enrich_prompt(prompt, character_name)
            if not reference_images:
                reference_images = character_bank.get_reference_images(character_name)

        adapter = self.get_adapter(model_name)
        request = GenerateRequest(
            prompt=prompt,
            params=params or {},
            reference_images=reference_images or [],
        )

        # Generate with verify-retry loop
        best_result = None
        best_score = 0.0
        result = None
        char_desc = character_bank.get_prompt_suffix(character_name) if character_bank and character_name else ""

        for attempt in range(MAX_RETRIES):
            result = await adapter.generate(request)
            verification = await self.verifier.verify_image(result.file_url, prompt, char_desc)
            result.metadata["quality_score"] = verification.score
            result.metadata["verification"] = {
                "passed": verification.passed,
                "dimensions": verification.dimensions,
                "explanation": verification.explanation,
            }

            if verification.score > best_score:
                best_score = verification.score
                best_result = result

            if verification.passed:
                return result

        # Return best attempt even if none passed
        return best_result or result

    async def generate_video(
        self,
        prompt: str,
        model_name: str = "veo",
        first_frame_image: str = "",
        character_bank: CharacterBank | None = None,
        character_name: str = "",
        params: dict | None = None,
    ) -> GenerateResult:
        """Generate a video clip with frame-chaining and quality verification."""

        if character_bank and character_name:
            prompt = character_bank.enrich_prompt(prompt, character_name)

        reference_images = [first_frame_image] if first_frame_image else []
        if character_bank and character_name and not reference_images:
            reference_images = character_bank.get_reference_images(character_name)

        adapter = self.get_adapter(model_name)
        request = GenerateRequest(
            prompt=prompt,
            params=params or {},
            reference_images=reference_images,
        )

        best_result = None
        best_score = 0.0
        result = None
        char_desc = character_bank.get_prompt_suffix(character_name) if character_bank and character_name else ""

        for attempt in range(MAX_RETRIES):
            result = await adapter.generate(request)
            verification = await self.verifier.verify_video(result.file_url, prompt, char_desc)
            result.metadata["quality_score"] = verification.score
            result.metadata["verification"] = {
                "passed": verification.passed,
                "dimensions": verification.dimensions,
                "explanation": verification.explanation,
            }

            if verification.score > best_score:
                best_score = verification.score
                best_result = result

            if verification.passed:
                return result

        return best_result or result

    async def generate_music(
        self,
        prompt: str,
        model_name: str = "acestep",
        params: dict | None = None,
    ) -> GenerateResult:
        """Generate music with verify-retry loop (consistent with image/video)."""
        adapter = self.get_adapter(model_name)
        request = GenerateRequest(prompt=prompt, params=params or {})

        best_result = None
        best_score = 0.0
        result = None

        for attempt in range(MAX_RETRIES):
            result = await adapter.generate(request)
            verification = await self.verifier.verify_music(result.file_url, prompt)
            result.metadata["quality_score"] = verification.score
            result.metadata["verification"] = {
                "passed": verification.passed,
                "dimensions": verification.dimensions,
                "explanation": verification.explanation,
            }
            if verification.score > best_score:
                best_score = verification.score
                best_result = result
            if verification.passed:
                return result

        return best_result or result

    @staticmethod
    def extract_last_frame(video_url: str, output_path: str) -> str:
        """Extract the last frame of a video for frame-chaining continuity.

        Uses FFmpeg to grab the final frame, which becomes the first-frame
        reference for the next shot. Supports HTTP(S) URLs (e.g. MinIO).
        """
        from app.core.shot_router import ShotRouter
        result = ShotRouter.extract_last_frame(video_url)
        if result and result != output_path:
            import shutil
            shutil.move(result, output_path)
        return output_path if result else ""
