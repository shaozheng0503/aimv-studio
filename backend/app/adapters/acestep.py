import asyncio
import os
from concurrent.futures import ThreadPoolExecutor

from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.config import get_settings


class ACEStepAdapter(BaseModelAdapter):
    name = "acestep"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        loop = asyncio.get_running_loop()
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = await loop.run_in_executor(
                pool, self._call_gradio, request, settings.acestep_base_url
            )
        return result

    def _call_gradio(self, request: GenerateRequest, base_url: str) -> GenerateResult:
        from gradio_client import Client
        from app.utils.storage import upload_file

        p = request.params or {}
        tags = p.get("description") or request.prompt or ""
        lyrics = p.get("lyrics", "") or ""
        bpm = float(p.get("bpm") or 0)
        duration = float(p.get("duration") or -1)
        instrumental = bool(p.get("instrumental", False))
        output_format = (p.get("format") or "wav").lower()
        if output_format not in {"wav", "mp3", "flac", "ogg"}:
            output_format = "wav"

        # ACEStep Gradio endpoint supports LoRA selection.
        lora_name_or_path = p.get("lora_name_or_path", "none") or "none"
        lora_weight = float(p.get("lora_weight", 1.0) or 1.0)

        if instrumental and not lyrics.strip():
            lyrics = "[inst]"

        if bpm > 0 and "bpm" not in tags.lower():
            tags = f"{tags}, {int(round(bpm))} BPM" if tags else f"{int(round(bpm))} BPM"

        infer_steps = int(p.get("infer_steps", 60))
        guidance_scale = float(p.get("guidance_scale", 15))
        scheduler_type = p.get("scheduler_type", "euler")
        cfg_type = p.get("cfg_type", "apg")
        omega_scale = float(p.get("omega_scale", 10))
        guidance_interval = float(p.get("guidance_interval", 0.5))
        guidance_interval_decay = float(p.get("guidance_interval_decay", 0))
        min_guidance_scale = float(p.get("min_guidance_scale", 3))
        use_erg_tag = bool(p.get("use_erg_tag", True))
        use_erg_lyric = bool(p.get("use_erg_lyric", False))
        use_erg_diffusion = bool(p.get("use_erg_diffusion", True))
        guidance_scale_text = float(p.get("guidance_scale_text", 0))
        guidance_scale_lyric = float(p.get("guidance_scale_lyric", 0))
        audio2audio_enable = bool(p.get("audio2audio_enable", False))
        ref_audio_strength = float(p.get("ref_audio_strength", 0.5))

        manual_seeds = p.get("manual_seeds", None)
        oss_steps = p.get("oss_steps", None)
        ref_audio_input = p.get("ref_audio_input", None)

        client = Client(base_url)
        result = client.predict(
            format=output_format,
            audio_duration=duration,
            prompt=tags,
            lyrics=lyrics,
            infer_step=infer_steps,
            guidance_scale=guidance_scale,
            scheduler_type=scheduler_type,
            cfg_type=cfg_type,
            omega_scale=omega_scale,
            manual_seeds=manual_seeds,
            guidance_interval=guidance_interval,
            guidance_interval_decay=guidance_interval_decay,
            min_guidance_scale=min_guidance_scale,
            use_erg_tag=use_erg_tag,
            use_erg_lyric=use_erg_lyric,
            use_erg_diffusion=use_erg_diffusion,
            oss_steps=oss_steps,
            guidance_scale_text=guidance_scale_text,
            guidance_scale_lyric=guidance_scale_lyric,
            audio2audio_enable=audio2audio_enable,
            ref_audio_strength=ref_audio_strength,
            ref_audio_input=ref_audio_input,
            lora_name_or_path=lora_name_or_path,
            lora_weight=lora_weight,
            api_name="/__call__",
        )

        # result[0] is the first audio sample filepath
        audio_raw = result[0] if result else None
        if audio_raw is None:
            raise RuntimeError("ACEStep returned no audio file")

        # gradio_client may return FileData objects (newer versions) or plain paths
        audio_path = audio_raw.path if hasattr(audio_raw, "path") else str(audio_raw)
        if not os.path.exists(audio_path):
            raise RuntimeError(f"ACEStep audio file not found at: {audio_path}")

        content_type = {
            "wav": "audio/wav",
            "flac": "audio/flac",
            "ogg": "audio/ogg",
            "mp3": "audio/mpeg",
        }.get(output_format, "audio/wav")
        file_url = upload_file(audio_path, content_type)
        return GenerateResult(
            file_url=file_url,
            duration=None,
            metadata={
                "model": "acestep",
                "base_url": base_url,
                "tags": tags,
                "format": output_format,
                "duration": duration,
                "lora_name_or_path": lora_name_or_path,
                "lora_weight": lora_weight,
            },
        )
