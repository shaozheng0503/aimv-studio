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
}


class GenerationService:

    def __init__(self):
        self.verifier = VerifierAgent()
        self._adapter_instances: dict[str, BaseModelAdapter] = {}

    def get_adapter(self, model_name: str) -> BaseModelAdapter:
        if model_name not in self._adapter_instances:
            adapter_cls = ADAPTER_MAP.get(model_name)
            if not adapter_cls:
                raise ValueError(f"Unknown model: {model_name}")
            self._adapter_instances[model_name] = adapter_cls()
        return self._adapter_instances[model_name]

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
            # Music quality: reuse image verifier prompt with audio-focused scoring
            verification = await self.verifier.verify_image(result.file_url, prompt)
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
