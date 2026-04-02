"""PlanningService — Orchestrates the CrewAI agents to produce a generation plan.

Flow:
1. User describes intent via chat
2. MusicAnalyzer processes uploaded/generated audio (if available)
3. Planning Crew runs: Screenwriter → Director → Music Producer
4. Results stored in Project (character_bank, storyboard, generation prompts)
"""

import json
import re
import asyncio
from app.core.agents.crew import build_planning_crew, build_review_crew
from app.core.music_analyzer import MusicAnalyzer, MusicAnalysis


class PlanningService:

    async def generate_plan(
        self,
        user_intent: str,
        audio_path: str | None = None,
        music_analysis: dict | None = None,
        visual_style: str = "",
        music_style: str = "",
        mood: str = "",
    ) -> dict:
        """Run the full planning pipeline and return structured plan.

        If music_analysis is provided (pre-computed from upload), it is used directly.
        If audio_path is provided (local path), MusicAnalyzer runs on it.
        """
        # Step 1: Analyze music — prefer pre-computed analysis, then local path
        music_data: dict = music_analysis or {}
        if not music_data and audio_path:
            def _analyze():
                analyzer = MusicAnalyzer(audio_path)
                try:
                    analysis = analyzer.analyze()
                    analyzer.separate_vocals()
                    analyzer.transcribe_lyrics()
                    return analysis.to_dict()
                finally:
                    analyzer.cleanup()
            music_data = await asyncio.to_thread(_analyze)

        # Step 2: Run planning crew (blocking → thread pool)
        crew = build_planning_crew(
            user_intent=user_intent,
            music_analysis=music_data,
            visual_style=visual_style,
            music_style=music_style,
            mood=mood,
        )
        result = await asyncio.to_thread(crew.kickoff)

        # Step 3: Merge the three task outputs into a single plan dict
        plan = self._merge_planning_tasks(result)

        # If Agent 3 (Music Producer) failed to parse, provide a style-aware fallback
        # so the pipeline always has a usable music_plan rather than generic defaults.
        if not plan.get("music_plan"):
            plan["music_plan"] = self._fallback_music_plan(
                visual_style=visual_style,
                music_style=music_style,
                mood=mood,
                music_data=music_data,
            )

        # Pass through music_analysis if not already embedded
        if music_data and not plan.get("music_analysis"):
            plan["music_analysis"] = music_data

        return plan

    @staticmethod
    def _fallback_music_plan(
        visual_style: str = "",
        music_style: str = "",
        mood: str = "",
        music_data: dict | None = None,
    ) -> dict:
        """Construct a reasonable music_plan when Agent 3 fails to produce one.

        Uses style/mood metadata so the fallback is contextually appropriate
        rather than a completely generic placeholder.
        """
        _style_prompts = {
            "赛博朋克": "Cyberpunk electronic music with driving synth basslines, glitch effects, and atmospheric pads. High energy, 120-140 BPM.",
            "国风": "Traditional Chinese instrumental with erhu, guzheng, and pipa. Cinematic and emotionally resonant, 70-90 BPM.",
            "韩娱": "K-pop inspired track with punchy beats, catchy hooks, and bright synths. Upbeat and polished, 95-115 BPM.",
            "幻想童话": "Magical orchestral fantasy score with harp, strings, and choir. Dreamy and whimsical, 75-95 BPM.",
            "复古迪斯科": "Disco-funk with electric bass, wah-wah guitar, brass stabs, and four-on-the-floor kick. Groovy, 110-120 BPM.",
            "独立电影": "Indie cinematic ambient with acoustic guitar, piano, and subtle strings. Emotionally nuanced, 60-85 BPM.",
            "都市甜酷": "Urban pop with lo-fi hip-hop beats, mellow keys, and smooth vocals. Chill yet stylish, 85-100 BPM.",
        }
        _mood_suffix = {
            "epic": " Epic, grand, and emotionally powerful. Build to an orchestral climax.",
            "energetic": " High energy, fast-paced, and exciting throughout.",
            "melancholic": " Melancholic and introspective. Slow build, bittersweet resolution.",
            "romantic": " Warm, tender, and emotionally intimate.",
            "peaceful": " Calm, serene, and meditative. Minimal arrangement.",
        }

        base_prompt = (
            _style_prompts.get(visual_style)
            or (f"{music_style} music track, cinematic quality." if music_style else
                "Cinematic instrumental music track. Emotional and atmospheric.")
        )
        base_prompt += _mood_suffix.get(mood, "")

        bpm = int(music_data.get("bpm", 0)) if music_data else 0
        needs_vocal = visual_style in {"韩娱", "赛博朋克"} and mood == "energetic"

        return {
            "music_prompt": base_prompt,
            "model_recommendation": "suno" if needs_vocal else "acestep",
            "needs_vocal": needs_vocal,
            "bpm": bpm,
            "key": "",
            "structure_map": [],
            "sync_points": [],
            "_fallback": True,  # flag so caller knows this is auto-generated
        }

    async def review_assets(
        self,
        storyboard: dict,
        generated_assets: list[dict],
        character_bank: dict,
    ) -> dict:
        """Run the review crew to verify generated content quality."""
        crew = build_review_crew(storyboard, generated_assets, character_bank)
        result = await asyncio.to_thread(crew.kickoff)
        obj = self._extract_json(str(result))
        return obj if isinstance(obj, dict) else {"raw_output": str(result)}

    # -------------------------------------------------------------------------
    # Internal helpers
    # -------------------------------------------------------------------------

    @staticmethod
    def _extract_json(text: str) -> dict | list | None:
        """Extract the first valid JSON value (dict or list) from a text blob.

        Strategy:
        1. Whole string as JSON.
        2. Last code fence (```json ... ```) that contains valid JSON.
        3. Scan from the first '[' or '{' character.
        """
        # 1. Whole string
        try:
            obj = json.loads(text)
            if isinstance(obj, (dict, list)):
                return obj
        except json.JSONDecodeError:
            pass

        # 2. Code fences — last fence first (final agent output is most complete)
        for fence in reversed(list(re.finditer(r"```(?:json)?\s*([\s\S]+?)\s*```", text))):
            try:
                obj = json.loads(fence.group(1))
                if isinstance(obj, (dict, list)):
                    return obj
            except json.JSONDecodeError:
                pass

        # 3. Scan for the first parseable JSON value
        decoder = json.JSONDecoder()
        for m in re.finditer(r"[\[{]", text):
            try:
                obj, _ = decoder.raw_decode(text, m.start())
                if isinstance(obj, (dict, list)):
                    return obj
            except json.JSONDecodeError:
                continue

        return None

    def _merge_planning_tasks(self, result) -> dict:
        """Merge outputs of the three planning tasks into one plan dict.

        Task layout:
          0 — Screenwriter   → {"character_bank": {...}, "storyboard": [...]}
          1 — Director       → JSON array of shot objects (each has segment_id + prompts)
          2 — Music Producer → {"music_plan": {...}}

        Each task is parsed independently so that no single task needs to repeat
        the full content of its predecessors.
        """
        tasks_output = getattr(result, "tasks_output", []) or []

        def _raw(idx: int) -> str:
            return getattr(tasks_output[idx], "raw", "") if idx < len(tasks_output) else ""

        # ---- Task 0: Screenwriter → character_bank + storyboard ----
        sw = self._extract_json(_raw(0)) or {}
        character_bank: dict = sw.get("character_bank", {}) if isinstance(sw, dict) else {}
        storyboard: list = sw.get("storyboard", []) if isinstance(sw, dict) else []

        # ---- Task 1: Director → shot objects (list or dict wrapping a list) ----
        dir_val = self._extract_json(_raw(1))
        if isinstance(dir_val, list):
            director_shots = dir_val
        elif isinstance(dir_val, dict):
            director_shots = (
                dir_val.get("storyboard") or dir_val.get("shots") or dir_val.get("segments") or []
            )
            # Fallback: if screenwriter produced nothing, use director's richer output
            if not character_bank:
                character_bank = dir_val.get("character_bank", {})
            if not storyboard:
                storyboard = dir_val.get("storyboard", [])
        else:
            director_shots = []

        # Merge director's per-shot fields into the screenwriter's storyboard.
        # Normalise segment_id to int for matching (LLM sometimes outputs "1" vs 1).
        if director_shots and storyboard:
            def _norm_id(v) -> int | str:
                try:
                    return int(v)
                except (TypeError, ValueError):
                    return v

            by_id = {
                _norm_id(s.get("segment_id")): s
                for s in director_shots
                if s.get("segment_id") is not None
            }
            for i, seg in enumerate(storyboard):
                sid = _norm_id(seg.get("segment_id"))
                shot = by_id.get(sid) or (director_shots[i] if i < len(director_shots) else {})
                for key in ("image_prompt", "negative_prompt", "video_prompt", "camera_direction", "model_recommendation"):
                    if key in shot and key not in seg:
                        seg[key] = shot[key]
        elif director_shots and not storyboard:
            storyboard = director_shots

        # ---- Task 2: Music Producer → music_plan ----
        mp = self._extract_json(_raw(2)) or {}
        if isinstance(mp, dict):
            music_plan: dict = mp.get("music_plan", {})
            # Fallback: if earlier tasks produced nothing, music producer may have the full plan
            if not character_bank:
                character_bank = mp.get("character_bank", {})
            if not storyboard:
                storyboard = mp.get("storyboard", [])
        else:
            music_plan = {}

        # ---- Last resort: parse the top-level result string ----
        if not (character_bank or storyboard or music_plan):
            fallback = self._extract_json(str(result))
            if isinstance(fallback, dict):
                return fallback
            return {"raw_output": str(result)}

        return {
            k: v for k, v in {
                "character_bank": character_bank,
                "storyboard": storyboard,
                "music_plan": music_plan,
            }.items() if v
        }
