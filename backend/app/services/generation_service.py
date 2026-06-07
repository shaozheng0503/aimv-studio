"""GenerationService — Dispatches generation tasks to model adapters.

Handles the full generate → verify → retry loop for each asset type.
Uses CharacterBank for prompt enrichment and VerifierAgent for quality gates.
"""

from typing import Callable, Awaitable

from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters.z_image import ZImageAdapter
from app.adapters.acestep import ACEStepAdapter
from app.adapters.suno import SunoAdapter
from app.adapters.lyria import LyriaAdapter
from app.adapters.wan_video import WanVideoAdapter
from app.adapters.seedance import SeedanceAdapter
from app.adapters.veo import VeoAdapter, Veo31Adapter, Veo31FastAdapter, Veo30Adapter, Veo20Adapter
from app.adapters.grok_video import GrokVideoAdapter
from app.adapters.google_image import GeminiImageAdapter, Imagen3Adapter, Imagen3FastAdapter
from app.core.character_bank import CharacterBank
from app.core.verifier import VerifierAgent, VerifyResult, MAX_RETRIES


ADAPTER_MAP: dict[str, type[BaseModelAdapter]] = {
    "z-image": ZImageAdapter,
    "acestep": ACEStepAdapter,
    "suno": SunoAdapter,
    "lyria": LyriaAdapter,
    "wan2.2": WanVideoAdapter,
    "seedance": SeedanceAdapter,
    # Veo: auto-cascade (newest → oldest) or pinned to a specific model
    "veo":          VeoAdapter,         # auto: 3.1 → 3.1-fast → 3.0 → 2.0
    "veo-3.1":      Veo31Adapter,       # pin: veo-3.1-generate-001
    "veo-3.1-fast": Veo31FastAdapter,   # pin: veo-3.1-fast-generate-001
    "veo-3.0":      Veo30Adapter,       # pin: veo-3.0-generate-001
    "veo-2.0":      Veo20Adapter,       # pin: veo-2.0-generate-001
    "grok": GrokVideoAdapter,
    # Google image models
    "gemini-image": GeminiImageAdapter,   # auto: Gemini 2.0 Flash → Imagen 3.0 fallback
    "imagen-3": Imagen3Adapter,           # pin: Imagen 3.0 on Vertex AI
    "imagen-3-fast": Imagen3FastAdapter,  # pin: Imagen 3.0 Fast (lower latency)
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
    # Planned — adapters not yet implemented; will raise ValueError if selected
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
    # Google image aliases
    "imagen 3": "imagen-3",
    "imagen3": "imagen-3",
    "imagen-3.0": "imagen-3",
    "imagen 3 fast": "imagen-3-fast",
    "imagen3fast": "imagen-3-fast",
    "gemini flash image": "gemini-image",
    # Veo display-name / frontend value → canonical adapter key
    "veo 3.1":           "veo-3.1",
    "veo3.1":            "veo-3.1",
    "veo 3.1 fast":      "veo-3.1-fast",
    "veo3.1fast":        "veo-3.1-fast",
    "veo 3.1-fast":      "veo-3.1-fast",
    "veo 3.0":           "veo-3.0",
    "veo3.0":            "veo-3.0",
    "veo 3":             "veo-3.1",
    "veo3":              "veo-3.1",
    "veo 2.0":           "veo-2.0",
    "veo2.0":            "veo-2.0",
    "veo 2":             "veo-2.0",
    "veo2":              "veo-2.0",
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

    async def _generate_with_retry(
        self,
        adapter: BaseModelAdapter,
        request: GenerateRequest,
        verify_fn: Callable[[str], Awaitable[VerifyResult]],
    ) -> GenerateResult:
        """Run generate → verify → retry loop; return best result across attempts."""
        best_result: GenerateResult | None = None
        best_score = 0.0
        result: GenerateResult | None = None

        for _ in range(MAX_RETRIES):
            result = await adapter.generate(request)
            verification = await verify_fn(result.file_url)
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

        return best_result or result  # type: ignore[return-value]

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
        if character_bank and character_name:
            prompt = character_bank.enrich_prompt(prompt, character_name)
            if not reference_images:
                reference_images = character_bank.get_reference_images(character_name)

        char_desc = character_bank.get_prompt_suffix(character_name) if character_bank and character_name else ""
        adapter = self.get_adapter(model_name)
        request = GenerateRequest(prompt=prompt, params=params or {}, reference_images=reference_images or [])
        return await self._generate_with_retry(
            adapter, request, lambda url: self.verifier.verify_image(url, prompt, char_desc)
        )

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

        char_desc = character_bank.get_prompt_suffix(character_name) if character_bank and character_name else ""
        adapter = self.get_adapter(model_name)
        request = GenerateRequest(prompt=prompt, params=params or {}, reference_images=reference_images)
        return await self._generate_with_retry(
            adapter, request, lambda url: self.verifier.verify_video(url, prompt, char_desc)
        )

    async def generate_music(
        self,
        prompt: str,
        model_name: str = "acestep",
        params: dict | None = None,
    ) -> GenerateResult:
        """Generate music with verify-retry loop (consistent with image/video)."""
        p = params or {}
        adapter = self.get_adapter(model_name)
        request = GenerateRequest(prompt=prompt, params=p)
        return await self._generate_with_retry(
            adapter, request,
            lambda url: self.verifier.verify_music(
                url, prompt,
                target_bpm=float(p.get("bpm") or 0),
                target_duration=float(p.get("duration") or 0),
            ),
        )

