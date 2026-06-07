"""Print raw crew output to understand the structure."""
import asyncio, sys
sys.path.insert(0, "/Users/huangshaozheng/Desktop/aimv/backend")
from dotenv import load_dotenv
load_dotenv("/Users/huangshaozheng/Desktop/aimv/backend/.env")

import asyncio
from app.core.agents.crew import build_planning_crew

async def main():
    crew = build_planning_crew(
        user_intent="孤独旅人星空MV，史诗风格",
        music_analysis={},
        visual_style="独立电影",
        mood="epic",
    )
    print("Running crew.kickoff()...")
    result = await asyncio.to_thread(crew.kickoff)
    raw = str(result)
    print(f"\n=== RAW OUTPUT (len={len(raw)}) ===")
    print(raw[:3000])
    print("...")
    if len(raw) > 3000:
        print(raw[-1000:])

asyncio.run(main())
