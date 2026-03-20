"""PlanningService — Orchestrates the CrewAI agents to produce a generation plan.

Flow:
1. User describes intent via chat
2. MusicAnalyzer processes uploaded/generated audio (if available)
3. Planning Crew runs: Screenwriter → Director → Music Producer
4. Results stored in Project (character_bank, storyboard, generation prompts)
"""

import json
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
                analysis = analyzer.analyze()
                # Separate vocals then transcribe lyrics for subtitle generation
                analyzer.separate_vocals()
                analyzer.transcribe_lyrics()
                return analysis.to_dict()
            music_data = await asyncio.to_thread(_analyze)

        # Step 2: Run planning crew — crew.kickoff() is blocking, offload to thread pool
        crew = build_planning_crew(
            user_intent=user_intent,
            music_analysis=music_data,
            visual_style=visual_style,
            music_style=music_style,
            mood=mood,
        )
        result = await asyncio.to_thread(crew.kickoff)

        # Step 3: Parse crew output
        # Try to extract per-task outputs (CrewAI >= 0.28 exposes tasks_output)
        plan = self._parse_crew_result(result)

        # Ensure music_analysis is always present (pass-through from input)
        if music_data and not plan.get("music_analysis"):
            plan["music_analysis"] = music_data

        # Normalise: crew may return music_plan nested or at top level
        if plan.get("music_plan") and not plan.get("music_prompt"):
            pass  # already in correct shape
        elif plan.get("music_prompt"):
            # Flat structure — lift into music_plan sub-dict
            plan["music_plan"] = {
                "music_prompt": plan.pop("music_prompt"),
                "model_recommendation": plan.pop("model_recommendation", "acestep"),
                "needs_vocal": plan.pop("needs_vocal", False),
                "structure_map": plan.pop("structure_map", []),
                "sync_points": plan.pop("sync_points", []),
            }

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
        return self._parse_crew_result(result)

    def _parse_crew_result(self, result) -> dict:
        """Extract structured data from CrewAI result.

        Strategy:
        1. Try parsing the entire string as JSON.
        2. Try content inside ```json ... ``` code fences.
        3. Scan for '{' and use json.JSONDecoder.raw_decode() — correctly
           handles braces inside strings (unlike the depth-counter approach).
        """
        import re
        raw = str(result)
        decoder = json.JSONDecoder()

        # 1. Whole string
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            pass

        # 2. Code fence
        fence = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", raw)
        if fence:
            try:
                return json.loads(fence.group(1))
            except json.JSONDecodeError:
                pass

        # 3. Scan for valid JSON objects starting at each '{'
        for m in re.finditer(r"\{", raw):
            try:
                obj, _ = decoder.raw_decode(raw, m.start())
                if isinstance(obj, dict):
                    return obj
            except json.JSONDecodeError:
                continue

        return {"raw_output": raw}
