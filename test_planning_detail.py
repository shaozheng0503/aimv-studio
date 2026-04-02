"""Detailed field-level validation of planning output."""
import asyncio, sys, json
sys.path.insert(0, "/Users/huangshaozheng/Desktop/aimv/backend")
from dotenv import load_dotenv
load_dotenv("/Users/huangshaozheng/Desktop/aimv/backend/.env")

from app.services.planning_service import PlanningService
from app.core.character_bank import CharacterBank

REQUIRED_SEG_FIELDS = ["segment_id", "label", "start_time", "end_time", "description", "mood", "characters"]
REQUIRED_PROMPT_FIELDS = ["image_prompt", "video_prompt", "camera_direction", "model_recommendation"]
VALID_MODELS = {"seedance", "veo", "grok", "wan2.2"}

async def main():
    svc = PlanningService()
    result = await svc.generate_plan(
        user_intent="帮我做一个关于孤独旅人在星空下徒步的MV，风格史诗感，配乐大气磅礴",
        visual_style="独立电影",
        music_style="Epic Orchestra",
        mood="epic",
    )

    errors = []
    warnings = []

    # ── Character Bank ───────────────────────────────────────────────
    print("\n── CHARACTER BANK ──")
    cb_raw = result.get("character_bank", {})
    cb = CharacterBank(cb_raw)
    for key, profile in cb.characters.items():
        suffix = profile.to_prompt_suffix()
        print(f"  [{key}]")
        print(f"    appearance type : {type(profile.appearance).__name__}")
        print(f"    outfit type     : {type(profile.outfit).__name__}")
        print(f"    to_prompt_suffix: {suffix[:80]}...")
        if not suffix:
            errors.append(f"character {key}: to_prompt_suffix() returned empty string")

    # ── Storyboard ───────────────────────────────────────────────────
    print("\n── STORYBOARD ──")
    storyboard = result.get("storyboard", [])
    sing_count = 0
    for seg in storyboard:
        sid = seg.get("segment_id")
        label = seg.get("label", "?")
        if label == "sing":
            sing_count += 1

        print(f"\n  [{sid}] {label}  {seg.get('start_time',0):.0f}s–{seg.get('end_time',0):.0f}s  mood={seg.get('mood','?')}")

        # Required narrative fields
        for f in REQUIRED_SEG_FIELDS:
            if f not in seg:
                errors.append(f"segment {sid}: missing field '{f}'")

        # Required prompt fields
        for f in REQUIRED_PROMPT_FIELDS:
            if f not in seg:
                errors.append(f"segment {sid}: missing Director field '{f}'")
            else:
                val = seg[f]
                print(f"    {f}: {str(val)[:70]}...")

        # negative_prompt check
        if "negative_prompt" not in seg:
            warnings.append(f"segment {sid}: missing 'negative_prompt'")
        else:
            print(f"    negative_prompt: {str(seg['negative_prompt'])[:60]}...")

        # model_recommendation validity
        rec = seg.get("model_recommendation", "")
        if rec not in VALID_MODELS:
            errors.append(f"segment {sid}: invalid model_recommendation '{rec}'")

        # sing → seedance check
        if label == "sing" and rec != "seedance":
            warnings.append(f"segment {sid}: label='sing' but model_recommendation='{rec}' (expected seedance)")

        # 16:9 in image_prompt
        ip = seg.get("image_prompt", "")
        if "16:9" not in ip:
            warnings.append(f"segment {sid}: image_prompt missing '16:9'")

        # frame-chaining transition hint in video_prompt
        vp = seg.get("video_prompt", "")
        if "transition hint" not in vp.lower():
            warnings.append(f"segment {sid}: video_prompt missing 'transition hint'")

        # duration hint in video_prompt
        if "second" not in vp.lower() and "duration" not in vp.lower():
            warnings.append(f"segment {sid}: video_prompt missing duration spec")

    if sing_count == 0:
        errors.append("No 'sing' segments found — MV has no performance shots")
    else:
        print(f"\n  Sing segments: {sing_count}/{len(storyboard)} ({100*sing_count//len(storyboard)}%)")

    # ── Music Plan ───────────────────────────────────────────────────
    print("\n── MUSIC PLAN ──")
    mp = result.get("music_plan", {})
    for f in ["music_prompt", "model_recommendation", "needs_vocal", "structure_map", "sync_points"]:
        if f not in mp:
            errors.append(f"music_plan missing '{f}'")
        else:
            val = mp[f]
            print(f"  {f}: {str(val)[:90]}...")

    # Check new fields: bpm, key
    for f in ["bpm", "key"]:
        if f not in mp:
            warnings.append(f"music_plan missing optional '{f}'")
        else:
            print(f"  {f}: {mp[f]}")

    # sync_points have musical_cue
    for sp in mp.get("sync_points", []):
        if "musical_cue" not in sp:
            warnings.append(f"sync_point at t={sp.get('time')} missing 'musical_cue'")

    # ── Summary ──────────────────────────────────────────────────────
    print("\n── VALIDATION SUMMARY ──")
    if errors:
        print(f"  ERRORS ({len(errors)}):")
        for e in errors:
            print(f"    ✗ {e}")
    else:
        print("  No errors ✓")

    if warnings:
        print(f"  WARNINGS ({len(warnings)}):")
        for w in warnings:
            print(f"    ⚠ {w}")
    else:
        print("  No warnings ✓")

asyncio.run(main())
