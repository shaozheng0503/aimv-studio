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
        max_tokens=2000,
    )


def create_screenwriter() -> Agent:
    return Agent(
        role="MV Screenwriter",
        goal=SCREENWRITER_GOAL,
        backstory=SCREENWRITER_BACKSTORY,
        verbose=False,
        allow_delegation=False,
        llm=_qwen_llm(),
    )


def create_director() -> Agent:
    return Agent(
        role="MV Visual Director",
        goal=DIRECTOR_GOAL,
        backstory=DIRECTOR_BACKSTORY,
        verbose=False,
        allow_delegation=False,
        llm=_qwen_llm(),
    )


def create_music_producer() -> Agent:
    return Agent(
        role="Music Producer",
        goal=MUSIC_PRODUCER_GOAL,
        backstory=MUSIC_PRODUCER_BACKSTORY,
        verbose=False,
        allow_delegation=False,
        llm=_qwen_llm(),
    )


def create_verifier() -> Agent:
    return Agent(
        role="Quality Director",
        goal=VERIFIER_GOAL,
        backstory=VERIFIER_BACKSTORY,
        verbose=False,
        allow_delegation=False,
        llm=_qwen_llm(),
    )


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
    screenwriter = create_screenwriter()
    director = create_director()
    music_producer = create_music_producer()

    context_block = f"""
## User Creative Intent
{user_intent}

## Music Analysis
BPM: {music_analysis.get('bpm', 'unknown')}
Duration: {music_analysis.get('duration', 'unknown')}s
Sections: {music_analysis.get('sections', [])}
Lyrics: {music_analysis.get('lyrics', [])}
Energy curve: {music_analysis.get('energy_curve', [])}

## Style Preferences
Visual style: {visual_style or 'auto'}
Music style: {music_style or 'auto'}
Mood: {mood or 'auto'}
"""

    task_screenwrite = Task(
        description=f"""Create a complete MV storyboard and character bank based on the following context.

{context_block}

Output a JSON object with two keys:
- "character_bank": dict of character profiles
- "storyboard": list of segment objects

Each segment: {{segment_id, label, start_time, end_time, description, mood, characters}}
Align segments with the music sections provided in the analysis.""",
        expected_output="JSON with character_bank and storyboard",
        agent=screenwriter,
    )

    task_direct = Task(
        description="""Based on the screenwriter's storyboard and character bank, create visual
generation prompts for each segment.

For each storyboard segment, output:
- image_prompt (English, detailed, optimized for AI image generation)
- video_prompt (English, includes motion and duration)
- camera_direction (subject, action, camera_movement, composition, lighting)
- model_recommendation (seedance/veo/grok/wan2.2)

Use frame-chaining: note that each shot's last frame will be the next shot's first frame.
Include the character descriptions from the character bank in every prompt.

Output as a JSON array of shot objects.""",
        expected_output="JSON array of shot objects with prompts and camera directions",
        agent=director,
        context=[task_screenwrite],
    )

    task_music = Task(
        description=f"""Based on the storyboard and visual direction plan, produce the COMPLETE
integrated production plan as a single JSON object. This is the final output that drives
the entire generation pipeline.

{context_block}

Output ONE JSON object with ALL four top-level keys:
- "character_bank": dict of character profiles from the Screenwriter (copy verbatim)
- "storyboard": list of segments — merge the Screenwriter's storyboard with the Director's
  shot objects so each segment has: segment_id, label, start_time, end_time, description,
  mood, characters, image_prompt, video_prompt, camera_direction, model_recommendation
- "music_plan": {{
    "music_prompt": "<detailed prompt>",
    "model_recommendation": "acestep" | "suno" | "lyria",
    "needs_vocal": true/false,
    "structure_map": [...],
    "sync_points": [{{time, event}}]
  }}
- "music_analysis": pass through the music analysis data unchanged (bpm, duration, sections, etc.)

All four keys must be present. Do not omit any.""",
        expected_output="Single JSON object with character_bank, storyboard, music_plan, and music_analysis",
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
    verifier = create_verifier()

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
