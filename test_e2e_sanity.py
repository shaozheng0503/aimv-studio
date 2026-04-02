"""End-to-end sanity check: text-only planning → pipeline params.

Verifies the full data flow from user intent to Celery task params
WITHOUT actually calling any AI model or DB.
"""
import asyncio, sys, json
sys.path.insert(0, "/Users/huangshaozheng/Desktop/aimv/backend")
from dotenv import load_dotenv
load_dotenv("/Users/huangshaozheng/Desktop/aimv/backend/.env")

from app.services.planning_service import PlanningService
from app.core.character_bank import CharacterBank
from app.core.shot_router import ShotRouter

INTENT = "帮我做一个赛博朋克风格的MV，主角是一个黑客少女，配乐电子感强，节奏快"

async def main():
    svc = PlanningService()
    print(f"Intent: {INTENT}\n")
    print("Running Planning Crew...")

    plan = await svc.generate_plan(
        user_intent=INTENT,
        visual_style="赛博朋克",
        music_style="Electronic",
        mood="energetic",
    )

    errors = []

    # ── 1. music_plan saved (simulated) ─────────────────────────────────────
    # Simulate what chat.py now does
    style_config = {}
    if plan.get("music_plan"):
        style_config["music_plan"] = plan["music_plan"]
    if plan.get("music_analysis"):
        style_config["music_analysis"] = plan["music_analysis"]

    mp = style_config.get("music_plan", {})
    if not mp:
        errors.append("CRITICAL: music_plan not in style_config after text-only planning")
    else:
        print(f"✓ music_plan saved (bpm={mp.get('bpm','?')} key={mp.get('key','?')} needs_vocal={mp.get('needs_vocal','?')})")
        print(f"  model: {mp.get('model_recommendation','?')}")
        print(f"  prompt[:80]: {mp.get('music_prompt','')[:80]}...")

    # ── 2. total_duration ────────────────────────────────────────────────────
    storyboard = plan.get("storyboard", [])
    total_duration = max((seg.get("end_time", 0) for seg in storyboard), default=180.0)
    print(f"\n✓ total_duration: {total_duration}s from {len(storyboard)} segments")

    # ── 3. music task params ─────────────────────────────────────────────────
    music_params = mp
    needs_vocal = bool(music_params.get("needs_vocal", False))
    music_task_params = {
        "prompt": music_params.get("music_prompt", "cinematic background music for music video"),
        "bpm": music_params.get("bpm", 0),
        "duration": total_duration,
        "instrumental": not needs_vocal,
    }
    if needs_vocal and music_params.get("lyrics_theme"):
        music_task_params["lyrics"] = music_params["lyrics_theme"]

    print(f"\n✓ Music task params:")
    for k, v in music_task_params.items():
        val = str(v)[:80] if isinstance(v, str) else v
        print(f"  {k}: {val}")

    if music_task_params["bpm"] == 0:
        print("  ⚠ bpm=0 (Agent didn't set it — ACEStep will auto-detect)")
    if music_task_params["duration"] < 10:
        errors.append(f"total_duration={total_duration} suspiciously short")

    # ── 4. ShotRouter with Agent 2 model_recommendation ─────────────────────
    router = ShotRouter()
    shot_plans = router.plan_all_shots(storyboard, "赛博朋克")
    print(f"\n✓ ShotRouter planned {len(shot_plans)} shots:")
    for p in shot_plans:
        seg_model_rec = next(
            (s.get("model_recommendation", "") for s in storyboard if s.get("segment_id") == p.segment_id),
            ""
        )
        override_used = seg_model_rec and seg_model_rec == p.video_model
        print(f"  [{p.segment_id}] {p.label:<6} model={p.video_model:<10} "
              f"neg_prompt={'YES' if p.negative_prompt else 'NO'} "
              f"{'← Agent2 override' if override_used else '← style routing'}")
        if not p.negative_prompt:
            errors.append(f"shot {p.segment_id}: negative_prompt empty in ShotPlan")

    # ── 5. CharacterBank prompt enrichment ──────────────────────────────────
    cb = CharacterBank(plan.get("character_bank", {}))
    print(f"\n✓ CharacterBank: {len(cb.characters)} character(s)")
    for name, char in cb.characters.items():
        suffix = char.to_prompt_suffix()
        print(f"  [{name}] suffix_len={len(suffix)} appearance_type={type(char.appearance).__name__}")
        if not suffix:
            errors.append(f"character {name}: to_prompt_suffix() is empty")
        else:
            print(f"    {suffix[:100]}...")

    # ── 6. Storyboard sing/story distribution ────────────────────────────────
    sing_segs = [s for s in storyboard if s.get("label") == "sing"]
    story_segs = [s for s in storyboard if s.get("label") == "story"]
    print(f"\n✓ sing/story: {len(sing_segs)} sing / {len(story_segs)} story")
    if not sing_segs:
        errors.append("No sing segments — MV has no performance shots")

    # ── 7. image_prompt quality check ────────────────────────────────────────
    missing_16x9 = [s["segment_id"] for s in storyboard if "16:9" not in s.get("image_prompt","")]
    missing_neg = [s["segment_id"] for s in storyboard if not s.get("negative_prompt")]
    missing_trans = [s["segment_id"] for s in storyboard if "transition hint" not in s.get("video_prompt","").lower()]
    if missing_16x9:
        print(f"  ⚠ segments missing '16:9' in image_prompt: {missing_16x9}")
    if missing_neg:
        errors.append(f"segments missing negative_prompt: {missing_neg}")
    if missing_trans:
        print(f"  ⚠ segments missing 'transition hint': {missing_trans}")

    print(f"\n{'─'*50}")
    if errors:
        print(f"ERRORS ({len(errors)}):")
        for e in errors:
            print(f"  ✗ {e}")
        sys.exit(1)
    else:
        print("All sanity checks passed ✓")

asyncio.run(main())
