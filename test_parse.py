"""Debug _parse_crew_result on the actual raw output."""
import sys, json, re
sys.path.insert(0, "/Users/huangshaozheng/Desktop/aimv/backend")

# Simulate what the crew returns (based on the raw output we saw)
# Read actual raw output
import asyncio
from dotenv import load_dotenv
load_dotenv("/Users/huangshaozheng/Desktop/aimv/backend/.env")
from app.core.agents.crew import build_planning_crew

async def main():
    crew = build_planning_crew(
        user_intent="孤独旅人星空MV，史诗风格",
        music_analysis={},
        visual_style="独立电影",
        mood="epic",
    )
    result = await asyncio.to_thread(crew.kickoff)
    raw = str(result)
    print(f"result.raw len={len(result.raw)}")
    print(f"str(result) len={len(raw)}")
    print(f"tasks_output count: {len(result.tasks_output)}")
    for i, t in enumerate(result.tasks_output):
        print(f"  task[{i}] raw len={len(t.raw)} agent={t.agent}")

    # Write full raw to file for inspection
    with open("/tmp/crew_raw.txt", "w") as f:
        f.write(result.raw)
    print(f"result.raw written to /tmp/crew_raw.txt")
    if result.tasks_output:
        with open("/tmp/crew_task_last.txt", "w") as f:
            f.write(result.tasks_output[-1].raw)
        print(f"last task raw written to /tmp/crew_task_last.txt")

    # Check code fences
    fences = list(re.finditer(r"```(?:json)?\s*([\s\S]+?)\s*```", raw))
    print(f"Code fences found: {len(fences)}")
    for i, fence in enumerate(fences):
        content = fence.group(1)
        print(f"  fence[{i}] len={len(content)} first50='{content[:50].replace(chr(10),' ')}'")
        try:
            obj = json.loads(content)
            print(f"    → valid JSON, keys={list(obj.keys())[:5]}")
        except Exception as e:
            print(f"    → PARSE ERROR: {e}")

    # Check json scan
    decoder = json.JSONDecoder()
    candidates = []
    for m in re.finditer(r"\{", raw):
        try:
            obj, end = decoder.raw_decode(raw, m.start())
            if isinstance(obj, dict):
                candidates.append((len(obj), list(obj.keys())[:4], m.start()))
        except:
            pass
    print(f"\nJSON scan found {len(candidates)} objects")
    PLAN_KEYS = {"storyboard","character_bank","music_plan"}
    for size, keys, pos in sorted(candidates, key=lambda x: (len(PLAN_KEYS & set(x[1])), x[0]), reverse=True)[:5]:
        print(f"  pos={pos} size={size} keys={keys}")

asyncio.run(main())
