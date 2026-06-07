import sys, os
sys.stdout.reconfigure(line_buffering=True)

import requests, json, time

BASE = "http://localhost:8000/api/v1"
OUT = open("/tmp/studio_test.log", "w", buffering=1)

def log(msg):
    print(msg)
    OUT.write(msg + "\n")
    OUT.flush()

log("=== 1. Login ===")
r = requests.post(f"{BASE}/auth/login", json={"username": "demo", "password": "demo123"}, timeout=10)
log(f"  status={r.status_code}")
if r.status_code != 200:
    log(f"  ERROR: {r.text}"); sys.exit(1)
token = r.json()["access_token"]
H = {"Authorization": f"Bearer {token}"}
log(f"  OK token={token[:25]}...")

log("\n=== 2. Create project ===")
r = requests.post(f"{BASE}/projects", json={"title": "Studio测试-孤独旅人"}, headers=H, timeout=10)
log(f"  status={r.status_code}")
proj = r.json(); pid = proj["id"]
log(f"  OK id={pid}")

log("\n=== 3. Chat round 1 ===")
msg = "帮我做一个关于孤独旅人在星空下徒步的MV，风格史诗感，配乐大气磅礴"
r = requests.post(f"{BASE}/projects/{pid}/chat",
    json={"message": msg, "generate_plan": False}, headers=H, timeout=60)
log(f"  status={r.status_code}")
resp = r.json()
log(f"  AI: {resp['content'][:300]}")
log(f"  intent: {resp.get('intent_extracted')}")

log("\n=== 4. Generate plan (CrewAI, may take ~60s) ===")
t0 = time.time()
r = requests.post(f"{BASE}/projects/{pid}/chat",
    json={"message": msg, "generate_plan": True}, headers=H, timeout=300)
elapsed = time.time() - t0
log(f"  status={r.status_code}  elapsed={elapsed:.1f}s")

if r.status_code != 200:
    log(f"  ERROR: {r.text[:300]}"); sys.exit(1)

resp2 = r.json()
plan = resp2.get("plan") or {}
sb = plan.get("storyboard", [])
cb = plan.get("character_bank", {})
mp = plan.get("music_plan", {})

log(f"  Summary: {resp2['content'][:200]}")
log(f"  storyboard segments: {len(sb)}")
for i, seg in enumerate(sb):
    log(f"    [{i+1}] {seg.get('label','?')} | {str(seg.get('description',''))[:80]}")
log(f"  characters: {list(cb.keys())}")
log(f"  music_plan: {json.dumps(mp, ensure_ascii=False)[:200]}")

if not sb:
    log("  ERROR: empty storyboard"); sys.exit(1)

log("\n=== 5. Build canvas nodes ===")
GRADIENTS = ["linear-gradient(135deg,#1a1a2e,#4a1fa8)","linear-gradient(135deg,#0f2027,#203a43)",
    "linear-gradient(135deg,#2d1b69,#11998e)","linear-gradient(135deg,#360033,#0b8793)",
    "linear-gradient(135deg,#1f1c2c,#928dab)"]
nodes, edges = [], []
nodes.append({"id":"song1","type":"song","position":{"x":60,"y":70},
    "data":{"title":(mp.get("music_prompt","") or "")[:20] or "生成中",
        "mood":"epic","bpm":plan.get("music_analysis",{}).get("bpm",120),
        "duration":180,"genre":"Epic Orchestra","description":mp.get("music_prompt",""),
        "lyrics":"","instrumental":True,"generateStatus":"idle","audioUrl":None}})
for i,(name,char) in enumerate(cb.items()):
    nodes.append({"id":f"char-{name}","type":"char","position":{"x":60,"y":280+i*180},
        "data":{"name":name,"description":char.get("description","") or char.get("appearance",""),
            "loraId":char.get("lora_id",""),"gender":char.get("gender","other")}})
for i,seg in enumerate(sb):
    sid = f"s{i+1}"
    nodes.append({"id":sid,"type":"shot","position":{"x":680+(i%3)*290,"y":55+(i//3)*220},
        "data":{"index":i+1,"prompt":seg.get("video_prompt") or seg.get("description",""),
            "model":seg.get("model_recommendation","Veo 3.1"),
            "duration":(seg.get("end_time",0) or 0)-(seg.get("start_time",0) or 0) or 5,
            "status":"pending","gradient":GRADIENTS[i%len(GRADIENTS)],
            "timeAnchor":seg.get("start_time"),"segment":seg.get("label"),"videoUrl":None}})
    edges.append({"id":f"e-song1-{sid}","source":"song1","target":sid,"type":"smoothstep","animated":True,
        "style":{"stroke":"rgba(141,92,255,0.4)","strokeWidth":1.5},"data":{"edgeType":"music-ref"}})
    if i > 0:
        edges.append({"id":f"e-s{i}-{sid}","source":f"s{i}","target":sid,"type":"smoothstep",
            "style":{"stroke":"rgba(255,255,255,0.15)","strokeWidth":1},"data":{"edgeType":"sequence"}})
log(f"  nodes={len(nodes)}: " + ", ".join(f"{n['type']}:{n['id']}" for n in nodes))
log(f"  edges={len(edges)}")

log("\n=== 6. Save canvas ===")
r = requests.put(f"{BASE}/projects/{pid}/canvas",
    json={"nodes":nodes,"edges":edges,"viewport":{}}, headers=H, timeout=20)
log(f"  status={r.status_code}  {r.text[:100]}")

log("\n=== 7. Start pipeline ===")
r = requests.post(f"{BASE}/projects/{pid}/pipeline/start", headers=H, timeout=20)
log(f"  status={r.status_code}  {r.json()}")

log("\n=== 8. Poll tasks every 8s for 80s ===")
for attempt in range(10):
    time.sleep(8)
    rp = requests.get(f"{BASE}/projects/{pid}", headers=H, timeout=10).json()
    rt = requests.get(f"{BASE}/projects/{pid}/tasks", headers=H, timeout=10)
    tasks = rt.json() if rt.status_code == 200 else []
    by_type = {}
    for t in tasks:
        by_type.setdefault(t["type"],[]).append(t["status"])
    log(f"  [{(attempt+1)*8:3d}s] status={rp.get('status')}  tasks={by_type}")
    if rp.get("status") in ("done","failed"):
        log("  Pipeline finished!"); break
    if "video" in by_type:
        log("  Video tasks started — stopping poll (video gen disabled)"); break

log(f"\n=== DONE ===")
log(f"  Studio: http://localhost:5173/studio/{pid}")
log(f"  Canvas: http://localhost:5173/canvas/{pid}")
OUT.close()
