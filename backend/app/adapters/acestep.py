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
        caption = p.get("description") or request.prompt or ""
        lyrics = p.get("lyrics", "") or ""
        bpm = float(p.get("bpm") or 0)
        duration = float(p.get("duration") or -1)
        vocal_language = p.get("vocal_language", "unknown") or "unknown"
        instrumental = bool(p.get("instrumental", False))

        if instrumental and not lyrics.strip():
            lyrics = "[Instrumental]"

        client = Client(base_url)
        result = client.predict(
            param_0=caption,
            param_1=lyrics,
            param_2=bpm,
            param_3="",        # key_scale (auto)
            param_4="",        # time_sig (auto)
            param_5=vocal_language,
            param_6=8.0,       # infer_steps (turbo default)
            param_7=7.0,       # guidance_scale
            param_8=True,      # random_seed
            param_9="-1",      # seed
            param_10=None,     # reference_audio (optional)
            param_11=duration,
            param_12=1,        # batch_size (must be int, server uses range())
            param_13=None,     # src_audio (optional)
            param_14="",       # lm_code_prompt
            param_15=0.0,      # repainting_start
            param_16=-1.0,     # repainting_end
            param_17="Fill the audio semantic mask based on the given conditions:",
            param_18=1.0,      # audio_cover_strength
            param_19="text2music",
            param_20=False,    # use_adg
            param_21=0.0,      # cfg_interval_start
            param_22=1.0,      # cfg_interval_end
            param_23=3.0,      # shift
            param_24="ode",    # infer_method
            param_25="",       # custom_timesteps
            param_26="mp3",    # audio_format
            param_27=0.85,     # lm_temperature
            param_28=False,    # think_checkbox — CoT causes CUDA assertion on short seqs
            param_29=2.0,      # lm_cfg_scale
            param_30=0.0,      # lm_top_k
            param_31=0.9,      # lm_top_p
            param_32="NO USER INPUT",  # lm_negative_prompt
            param_33=True,     # use_cot_metas
            param_34=True,     # use_cot_caption (description rewrite)
            param_35=True,     # use_cot_language
            # param_36 not exposed in API
            param_37=False,    # constrained_decoding_debug
            param_38=True,     # allow_lm_batch (parallel thinking)
            param_39=False,    # auto_score
            param_40=False,    # auto_lrc
            param_41=0.5,      # score_scale
            param_42=8.0,      # lm_batch_chunk_size
            param_43="vocals", # track_name
            param_44=[],       # complete_track_classes
            param_45=False,    # auto_generate
            api_name="/generation_wrapper",
        )

        # result[0] is the first audio sample filepath
        audio_raw = result[0] if result else None
        if audio_raw is None:
            raise RuntimeError("ACEStep returned no audio file")

        # gradio_client may return FileData objects (newer versions) or plain paths
        audio_path = audio_raw.path if hasattr(audio_raw, "path") else str(audio_raw)
        if not os.path.exists(audio_path):
            raise RuntimeError(f"ACEStep audio file not found at: {audio_path}")

        file_url = upload_file(audio_path, "audio/mpeg")
        return GenerateResult(
            file_url=file_url,
            duration=None,
            metadata={"model": "acestep-v15-turbo", "caption": caption},
        )
