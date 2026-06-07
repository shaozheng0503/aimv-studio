"""Direct test of PlanningService to debug empty storyboard."""
import asyncio, sys, json
sys.path.insert(0, "/Users/huangshaozheng/Desktop/aimv/backend")

# Load env
from dotenv import load_dotenv
load_dotenv("/Users/huangshaozheng/Desktop/aimv/backend/.env")

from app.services.planning_service import PlanningService

async def main():
    svc = PlanningService()
    print("Calling generate_plan...")

    result = await svc.generate_plan(
        user_intent="帮我做一个关于孤独旅人在星空下徒步的MV，风格史诗感，配乐大气磅礴",
        visual_style="独立电影",
        music_style="Epic Orchestra",
        mood="epic",
    )

    print("\n=== Result keys:", list(result.keys()))
    print("storyboard count:", len(result.get("storyboard", [])))
    print("character_bank:", list(result.get("character_bank", {}).keys()))

    if result.get("raw_output"):
        print("\n=== RAW OUTPUT (JSON parse failed) ===")
        print(result["raw_output"][:2000])
    else:
        print("\n=== PARSED OK ===")
        for i, seg in enumerate(result.get("storyboard", [])):
            print(f"  [{i+1}] {seg.get('label','?')} | {str(seg.get('description',''))[:60]}")
        print("music_plan:", json.dumps(result.get("music_plan",{}), ensure_ascii=False)[:200])

asyncio.run(main())
