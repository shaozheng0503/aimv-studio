"""PlanningService — Orchestrates the CrewAI agents to produce a generation plan.

Flow:
1. User describes intent via chat
2. MusicAnalyzer processes uploaded/generated audio (if available)
3. Planning Crew runs: Screenwriter → Director → Music Producer
4. Results stored in Project (character_bank, storyboard, generation prompts)
"""

import json
from app.core.agents.crew import build_planning_crew, build_review_crew
from app.core.music_analyzer import MusicAnalyzer, MusicAnalysis


class PlanningService:

    async def generate_plan(
        self,
        user_intent: str,
        audio_path: str | None = None,
        visual_style: str = "",
        music_style: str = "",
        mood: str = "",
    ) -> dict:
        """Run the full planning pipeline and return structured plan."""

        # Step 1: Analyze music (if audio provided)
        music_data = {}
        if audio_path:
            analyzer = MusicAnalyzer(audio_path)
            analysis = analyzer.analyze()
            # Separate vocals then transcribe lyrics for subtitle generation
            analyzer.separate_vocals()
            analyzer.transcribe_lyrics()
            music_data = analysis.to_dict()

        # Step 2: Run planning crew
        crew = build_planning_crew(
            user_intent=user_intent,
            music_analysis=music_data,
            visual_style=visual_style,
            music_style=music_style,
            mood=mood,
        )
        result = crew.kickoff()

        # Step 3: Parse crew output
        plan = self._parse_crew_result(result)
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
        result = crew.kickoff()
        return self._parse_crew_result(result)

    def _parse_crew_result(self, result) -> dict:
        """Extract structured data from CrewAI result."""
        raw = str(result)

        # Try to find JSON in the output
        try:
            # Look for the outermost JSON object or array
            start = raw.find("{")
            if start == -1:
                start = raw.find("[")
            if start != -1:
                # Find matching closing bracket
                depth = 0
                opener = raw[start]
                closer = "}" if opener == "{" else "]"
                for i in range(start, len(raw)):
                    if raw[i] == opener:
                        depth += 1
                    elif raw[i] == closer:
                        depth -= 1
                    if depth == 0:
                        return json.loads(raw[start : i + 1])
        except (json.JSONDecodeError, IndexError):
            pass

        return {"raw_output": raw}
