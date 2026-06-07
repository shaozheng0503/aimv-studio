"""Test the Studio agent flow: login → create project → chat → plan → pipeline start → poll progress"""
import requests, json, time, sys

BASE = "http://localhost:8000/api/v1"

# ── 1. Login ────────────────────────────────────────────────────────────────
print("=== 1. Login ===")
r = requests.post(f"{BASE}/auth/login", json={"username": "demo", "password": "demo123"})
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
print(f"  OK  token={token[:30]}...")

# ── 2. Create project ────────────────────────────────────────────────────────
print("\n=== 2. Create project ===")
r = requests.post(f"{BASE}/projects", json={"title": "测试Studio流程"}, headers=H)
proj = r.json()
pid = proj["id"]
print(f"  OK  id={pid}  title={proj['title']}")

# ── 3. Chat round 1 — describe idea ─────────────────────────────────────────
print("\n=== 3. Chat round 1: describe MV idea ===")
msg = "帮我做一个关于孤独旅人在星空下徒步的MV，风格偏史诗感，配乐大气磅礴"
r = requests.post(f"{BASE}/projects/{pid}/chat",
    json={"message": msg, "generate_plan": False}, headers=H)
resp = r.json()
print(f"  User: {msg}")
print(f"  AI:   {resp['content'][:200]}...")
if resp.get("intent_extracted"):
    print(f"  Intent: {resp['intent_extracted']}")

# ── 4. Update project with intent ────────────────────────────────────────────
print("\n=== 4. Update project settings ===")
intent = resp.get("intent_extracted") or {}
update = {k: v for k, v in {
    "visual_style": intent.get("visual_style"),
    "mood": intent.get("mood"),
    "music_style": intent.get("music_style"),
}.items() if v}
if update:
    r = requests.put(f"{BASE}/projects/{pid}", json=update, headers=H)
    print(f"  OK  updated: {update}")
else:
    print("  (no intent extracted yet)")

# ── 5. Generate plan ─────────────────────────────────────────────────────────
print("\n=== 5. Generate plan (generate_plan=true) ===")
print("  Calling CrewAI planning... (may take 30-90s)")
t0 = time.time()
r = requests.post(f"{BASE}/projects/{pid}/chat",
    json={"message": msg, "generate_plan": True}, headers=H, timeout=180)
elapsed = time.time() - t0
resp2 = r.json()
plan = resp2.get("plan", {})

print(f"  Done in {elapsed:.1f}s")
print(f"  AI summary: {resp2['content'][:200]}...")

sb = plan.get("storyboard", [])
cb = plan.get("character_bank", {})
mp = plan.get("music_plan", {})

print(f"\n  Storyboard segments: {len(sb)}")
for i, seg in enumerate(sb):
    print(f"    [{i+1}] {seg.get('label','?')} | {seg.get('description','')[:60]}...")

print(f"\n  Characters: {list(cb.keys())}")
print(f"\n  Music plan: {json.dumps(mp, ensure_ascii=False)[:200]}")

if not sb:
    print("\n  ERROR: Empty storyboard, aborting.")
    sys.exit(1)

# ── 6. Build canvas nodes ────────────────────────────────────────────────────
print("\n=== 6. Build canvas from plan ===")
GRADIENTS = [
    "linear-gradient(135deg,#1a1a2e,#4a1fa8)",
    "linear-gradient(135deg,#0f2027,#203a43)",
    "linear-gradient(135deg,#2d1b69,#11998e)",
    "linear-gradient(135deg,#360033,#0b8793)",
    "linear-gradient(135deg,#1f1c2c,#928dab)",
]
nodes, edges = [], []

nodes.append({"id": "song1", "type": "song", "position": {"x": 60, "y": 70},
    "data": {
        "title": (mp.get("music_prompt","") or "")[:20] or "生成中",
        "mood": intent.get("mood","energetic"),
        "bpm": plan.get("music_analysis",{}).get("bpm", 120),
        "duration": plan.get("music_analysis",{}).get("duration", 180),
        "genre": intent.get("music_style","Epic"),
        "description": mp.get("music_prompt",""),
        "lyrics": "", "instrumental": True,
        "generateStatus": "idle", "audioUrl": None,
    }
})

for i, (name, char) in enumerate(cb.items()):
    nodes.append({"id": f"char-{name}", "type": "char",
        "position": {"x": 60, "y": 280 + i*180},
        "data": {"name": name, "description": char.get("description","") or char.get("appearance",""),
                 "loraId": char.get("lora_id",""), "gender": char.get("gender","other")}
    })

for i, seg in enumerate(sb):
    sid = f"s{i+1}"
    nodes.append({"id": sid, "type": "shot",
        "position": {"x": 680 + (i%3)*290, "y": 55 + (i//3)*220},
        "data": {
            "index": i+1,
            "prompt": seg.get("video_prompt") or seg.get("description",""),
            "model": seg.get("model_recommendation","Veo 3.1"),
            "duration": (seg.get("end_time",0) or 0) - (seg.get("start_time",0) or 0) or 5,
            "status": "pending", "gradient": GRADIENTS[i % len(GRADIENTS)],
            "timeAnchor": seg.get("start_time"), "segment": seg.get("label"), "videoUrl": None,
        }
    })
    edges.append({"id": f"e-song1-{sid}", "source":"song1","target":sid,
        "type":"smoothstep","animated":True,
        "style":{"stroke":"rgba(141,92,255,0.4)","strokeWidth":1.5},
        "data":{"edgeType":"music-ref"}})
    if i > 0:
        edges.append({"id": f"e-s{i}-{sid}", "source":f"s{i}","target":sid,
            "type":"smoothstep","style":{"stroke":"rgba(255,255,255,0.15)","strokeWidth":1},
            "data":{"edgeType":"sequence"}})

print(f"  Built {len(nodes)} nodes, {len(edges)} edges")
for n in nodes:
    print(f"    {n['type']:8s}  {n['id']:15s}  {str(n['data'].get('prompt') or n['data'].get('description') or n['data'].get('title',''))[:50]}")

# ── 7. Save canvas ───────────────────────────────────────────────────────────
print("\n=== 7. Save canvas ===")
r = requests.put(f"{BASE}/projects/{pid}/canvas",
    json={"nodes": nodes, "edges": edges, "viewport": {}}, headers=H)
print(f"  HTTP {r.status_code}  {r.text[:100]}")

# ── 8. Start pipeline ────────────────────────────────────────────────────────
print("\n=== 8. Start pipeline ===")
r = requests.post(f"{BASE}/projects/{pid}/pipeline/start", headers=H)
print(f"  HTTP {r.status_code}  {r.json()}")

if r.status_code != 200:
    print("  Pipeline failed to start")
    sys.exit(1)

# ── 9. Poll project status & tasks ───────────────────────────────────────────
print("\n=== 9. Polling progress (60s) ===")
for attempt in range(12):
    time.sleep(5)
    r = requests.get(f"{BASE}/projects/{pid}", headers=H)
    p = r.json()
    # Get tasks
    rt = requests.get(f"{BASE}/projects/{pid}/tasks", headers=H)
    tasks = rt.json() if rt.status_code == 200 else []

    task_summary = {}
    for t in tasks:
        ttype = t.get("type","?")
        tstatus = t.get("status","?")
        task_summary.setdefault(ttype, []).append(tstatus)

    print(f"  [{attempt*5:3d}s] project.status={p.get('status')}  tasks={dict(task_summary)}")

    if p.get("status") in ("done", "failed"):
        print(f"  Pipeline finished: {p.get('status')}")
        break

    # Check if we have image or music tasks running
    all_types = [t.get("type") for t in tasks]
    if "video" in all_types and attempt >= 2:
        print("\n  Video tasks appeared — stopping poll (video gen disabled for this test)")
        break

print("\n=== Done ===")
print(f"  Project URL: http://localhost:5173/studio/{pid}")
print(f"  Canvas URL:  http://localhost:5173/canvas/{pid}")
