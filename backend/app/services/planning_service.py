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

        # Pass through music_analysis if not already embedded
        if music_data and not plan.get("music_analysis"):
            plan["music_analysis"] = music_data

        return plan

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

        # Merge director's per-shot fields into the screenwriter's storyboard
        if director_shots and storyboard:
            by_id = {s.get("segment_id"): s for s in director_shots if s.get("segment_id")}
            for i, seg in enumerate(storyboard):
                shot = by_id.get(seg.get("segment_id")) or (director_shots[i] if i < len(director_shots) else {})
                for key in ("image_prompt", "video_prompt", "camera_direction", "model_recommendation"):
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
