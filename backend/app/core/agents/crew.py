"""CrewAI-based orchestration for MV creation pipeline.

Defines 4 Agent roles (Screenwriter, Director, Music Producer, Verifier)
and the task flow from user intent to generation-ready prompts.
"""

from crewai import Agent, Task, Crew, Process, LLM
from app.core.agents.prompts import (
    SCREENWRITER_BACKSTORY, SCREENWRITER_GOAL,
    DIRECTOR_BACKSTORY, DIRECTOR_GOAL,
    MUSIC_PRODUCER_BACKSTORY, MUSIC_PRODUCER_GOAL,
    VERIFIER_BACKSTORY, VERIFIER_GOAL,
)

# Agent configuration: name → (role, goal, backstory)
_AGENT_CONFIGS: dict[str, tuple[str, str, str]] = {
    "screenwriter": ("MV Screenwriter", SCREENWRITER_GOAL, SCREENWRITER_BACKSTORY),
    "director": ("MV Visual Director", DIRECTOR_GOAL, DIRECTOR_BACKSTORY),
    "music_producer": ("Music Producer", MUSIC_PRODUCER_GOAL, MUSIC_PRODUCER_BACKSTORY),
    "verifier": ("Quality Director", VERIFIER_GOAL, VERIFIER_BACKSTORY),
}


def _qwen_llm() -> LLM | None:
    """Return a CrewAI LLM pointing to the Qwen endpoint, or None to use default."""
    from app.config import get_settings
    s = get_settings()
    if not s.qwen_base_url:
        return None
    return LLM(
        model=f"openai/{s.qwen_model}",
        base_url=f"{s.qwen_base_url.rstrip('/')}/v1",
        api_key="dummy",
        temperature=0.7,
        max_tokens=8192,
    )


def _create_agent(name: str, llm: LLM | None = None) -> Agent:
    """Create an agent by name from the configuration table."""
    role, goal, backstory = _AGENT_CONFIGS[name]
    return Agent(
        role=role, goal=goal, backstory=backstory,
        verbose=False, allow_delegation=False, llm=llm,
    )


def _summarize_energy_curve(curve: list) -> str:
    """Return a compact energy curve summary for injection into LLM context."""
    if not curve:
        return "N/A"
    n = len(curve)
    # Show ~10 representative points with timestamps
    step = max(1, n // 10)
    points = [(i, round(curve[i], 2)) for i in range(0, n, step)]
    return "  ".join(f"{i}s:{v}" for i, v in points)


def build_planning_crew(
    user_intent: str,
    music_analysis: dict,
    visual_style: str = "",
    music_style: str = "",
    mood: str = "",
) -> Crew:
    """Build a CrewAI crew for the planning phase (intent → storyboard + prompts).

    This crew runs sequentially:
    1. Screenwriter analyzes intent + music → character bank + storyboard
    2. Director converts storyboard → image/video prompts + camera directions
    3. Music Producer designs music prompt aligned with visual plan
    """
    llm = _qwen_llm()
    screenwriter = _create_agent("screenwriter", llm)
    director = _create_agent("director", llm)
    music_producer = _create_agent("music_producer", llm)

    duration = music_analysis.get("duration") or 0
    # Target segment count: 1 per 20-25s, clamped to [4, 10]
    target_segments = max(4, min(10, round(duration / 22))) if duration else 6
    # Minimum sing segments: ceil(25% of total)
    min_sing = max(1, -(-target_segments // 4))  # ceiling division

    sections = music_analysis.get("sections", [])
    sections_str = (
        "\n".join(
            f"  {s.get('label','?')} {s.get('start',0):.1f}s–{s.get('end',0):.1f}s  energy={s.get('energy',0):.2f}"
            for s in sections
        )
        if sections else "  (no sections detected)"
    )

    energy_summary = _summarize_energy_curve(music_analysis.get("energy_curve", []))

    lyrics_lines = music_analysis.get("lyrics", [])
    lyrics_str = (
        "\n".join(f"  [{l.get('start',0):.1f}s–{l.get('end',0):.1f}s] {l.get('text','')}" for l in lyrics_lines[:20])
        if lyrics_lines else "  (no lyrics detected / instrumental)"
    )

    context_block = f"""## User Creative Intent
{user_intent}

## Music Analysis
BPM: {music_analysis.get('bpm', 'unknown')}
Duration: {duration or 'unknown'}s
Song sections:
{sections_str}
Energy curve (second: energy 0-1):
  {energy_summary}
Lyrics:
{lyrics_str}

## Style Preferences
Visual style: {visual_style or 'auto'}
Music style: {music_style or 'auto'}
Mood: {mood or 'auto'}

## Storyboard Requirements
Target segments: {target_segments} (one per ~20-25 seconds)
Minimum "sing" segments: {min_sing} (at chorus/high-energy sections)
Minimum segment duration: 10 seconds
Maximum segment duration: 40 seconds"""

    task_screenwrite = Task(
        description=f"""Create a complete MV storyboard and character bank.

{context_block}

Output a single JSON object with exactly two keys:
- "character_bank": dict of character profiles (appearance and outfit as prose English strings)
- "storyboard": list of exactly {target_segments} segment objects

Storyboard rules:
1. segment_id must be sequential integers starting at 1
2. At least {min_sing} segments must have label "sing" (place them at high-energy sections)
3. Align start_time/end_time with the song sections above
4. description must be 2-3 vivid English sentences describing the shot
5. characters list uses the character_bank key (e.g. "The_Wanderer"), empty [] for landscape shots

Output JSON only — no explanation, no markdown fence.""",
        expected_output='{"character_bank": {...}, "storyboard": [...]}',
        agent=screenwriter,
    )

    task_direct = Task(
        description=f"""Based on the screenwriter's storyboard and character bank, create AI-generation-ready
visual prompts for every segment.

Visual style anchor: {visual_style or 'cinematic'}
Aspect ratio for ALL prompts: 16:9

For each storyboard segment output one JSON object. Collect all objects into a JSON array.

Required fields per shot:
- segment_id: integer (copy exactly from storyboard)
- image_prompt: detailed English prompt (include 16:9, 8K, art-style keywords, full character prose)
- negative_prompt: what to avoid (always include "watermark, text, blurry, distorted anatomy, artifacts")
- video_prompt: image_prompt content + motion description + duration + transition hint
- camera_direction: {{subject, action, camera_movement, composition, lighting, ambiance}}
- model_recommendation: one of "seedance" | "veo" | "grok" | "wan2.2"

Frame-chaining rule: each shot's video_prompt must end with
  "transition hint: <fade/cut/dissolve> to <brief next-scene description>"

Model selection:
- "sing" label → always "seedance"
- montage/fast-cut/abstract → always "grok"
- cinematic landscape/narrative → "veo"

Output ONLY a JSON array — no wrapper dict, no explanation.""",
        expected_output="JSON array of shot objects",
        agent=director,
        context=[task_screenwrite],
    )

    task_music = Task(
        description=f"""Design the complete music generation plan for this MV.

Music style preference: {music_style or 'auto'}
Mood: {mood or 'auto'}
Total duration target: {duration or 180}s

Use the energy curve summary to place musical peaks at visual climax points:
  {energy_summary}

Output ONLY this JSON (do NOT repeat storyboard or character_bank):
{{
  "music_plan": {{
    "music_prompt": "<detailed English prompt>",
    "model_recommendation": "acestep" | "suno" | "lyria",
    "needs_vocal": true | false,
    "bpm": <int>,
    "key": "<e.g. C# minor>",
    "structure_map": [
      {{"section": "<name>", "start_time": 0.0, "end_time": 30.0, "description": "<what music does + why it matches visual>"}}
    ],
    "sync_points": [
      {{"time": 0.0, "event": "<specific visual moment>", "musical_cue": "<beat drop / orchestral hit / silence>"}}
    ]
  }}
}}

music_prompt must specify: genre, mood arc, BPM range, key, instrumentation, structure, reference artists.""",
        expected_output='{"music_plan": {...}}',
        agent=music_producer,
        context=[task_screenwrite, task_direct],
    )

    return Crew(
        agents=[screenwriter, director, music_producer],
        tasks=[task_screenwrite, task_direct, task_music],
        process=Process.sequential,
        verbose=False,
    )


def build_review_crew(
    storyboard: dict,
    generated_assets: list[dict],
    character_bank: dict,
) -> Crew:
    """Build a CrewAI crew for the review phase (verify generated content quality)."""
    verifier = _create_agent("verifier", _qwen_llm())

    task_review = Task(
        description=f"""Review the following generated MV assets against the original plan.

## Storyboard
{storyboard}

## Character Bank
{character_bank}

## Generated Assets
{generated_assets}

For each asset:
1. Score on 1-5 scale (visual_quality, character_consistency, prompt_adherence, physical_plausibility)
2. Flag assets scoring below 3 for regeneration
3. Provide specific improvement suggestions

Output a JSON object with:
- "overall_score": float
- "passed": boolean (true if all assets >= 3)
- "asset_reviews": list of per-asset review objects
- "regenerate_ids": list of asset IDs that need regeneration""",
        expected_output="JSON quality report",
        agent=verifier,
    )

    return Crew(
        agents=[verifier],
        tasks=[task_review],
        process=Process.sequential,
        verbose=False,
    )
