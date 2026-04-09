#!/usr/bin/env python3
"""
Google API integration tests: Gemini image gen + Veo video gen
Tests: text→image (3 rounds), text→video (4/6/8s), image→video (2 rounds)

Usage:
  cd /Users/huangshaozheng/Desktop/aimv
  python3 test_google_api.py
"""

import asyncio
import base64
import os
import shutil
import sys
import time
import traceback
import uuid
from pathlib import Path
from types import ModuleType

# ── backend on path ────────────────────────────────────────────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
_BACKEND = os.path.join(_ROOT, "backend")
sys.path.insert(0, _BACKEND)

# Set absolute SA path BEFORE any app import (pydantic-settings reads env at first call)
_SA_PATH = os.path.join(_BACKEND, ".credentials", "gcp-sa.json")
if os.path.exists(_SA_PATH):
    os.environ.setdefault("GOOGLE_SA_PATH", _SA_PATH)
else:
    print(f"WARNING: SA file not found at {_SA_PATH}")
    sys.exit(1)

# ── inject mock storage BEFORE any app import ─────────────────────────────────
SAVE_DIR = "/tmp/aimv_google_test"
os.makedirs(SAVE_DIR, exist_ok=True)
_saved: list[dict] = []

def _mock_upload(local_path: str, content_type: str = "application/octet-stream") -> str:
    ext = Path(local_path).suffix or (".mp4" if "video" in content_type else ".png")
    dest = os.path.join(SAVE_DIR, f"{uuid.uuid4().hex}{ext}")
    shutil.copy2(local_path, dest)
    size_kb = os.path.getsize(dest) // 1024
    _saved.append({"path": dest, "size_kb": size_kb, "type": content_type})
    print(f"      💾  {dest}  ({size_kb} KB)")
    return dest

_mock_mod = ModuleType("app.utils.storage")
_mock_mod.upload_file = _mock_upload  # type: ignore
sys.modules["app.utils.storage"] = _mock_mod

# ── now safe to import app code ────────────────────────────────────────────────
from app.adapters.base import GenerateRequest  # noqa: E402
from app.adapters.google_image import GeminiImageAdapter, Imagen3Adapter  # noqa: E402
from app.adapters.veo import VeoAdapter, Veo31Adapter, Veo31FastAdapter, Veo30Adapter, Veo20Adapter  # noqa: E402

# ── helpers ────────────────────────────────────────────────────────────────────
PASS = "\033[32m✓\033[0m"
FAIL = "\033[31m✗\033[0m"
WARN = "\033[33m⚠\033[0m"
results: list[dict] = []


async def run_case(label: str, coro):
    print(f"   ▶  {label} …", flush=True)
    t0 = time.time()
    try:
        result = await coro
        elapsed = time.time() - t0
        model = result.metadata.get("model", "?")
        print(f"   {PASS}  {label}  ({elapsed:.1f}s)  model={model}")
        results.append({"label": label, "ok": True, "elapsed": elapsed,
                         "model": model, "url": result.file_url})
        return result
    except Exception as e:
        elapsed = time.time() - t0
        print(f"   {FAIL}  {label}  ({elapsed:.1f}s)")
        print(f"         ERROR: {e}")
        traceback.print_exc()
        results.append({"label": label, "ok": False, "elapsed": elapsed, "error": str(e)})
        return None


# ── duration clamp unit test ───────────────────────────────────────────────────
def test_duration_clamp() -> bool:
    print("\n" + "─" * 62)
    print("⚙️   UNIT TEST: Veo duration clamp (4 / 6 / 8 s only)")
    print("─" * 62)
    _VALID = (4, 6, 8)   # Veo 3.x constraint (4/6/8s)
    cases = {1: 4, 4: 4, 5: 4, 6: 6, 7: 6, 8: 8, 9: 8, 10: 8, 30: 8}
    ok = True
    for raw, expected in cases.items():
        got = min(_VALID, key=lambda d: abs(d - raw))
        sym = PASS if got == expected else FAIL
        print(f"   {sym}  input={raw:2d}s → clamped={got}s")
        if got != expected:
            ok = False
    return ok


# ── image generation ───────────────────────────────────────────────────────────
async def test_image():
    print("\n" + "─" * 62)
    print("📸  IMAGE GENERATION")
    print("    Gemini 2.0 Flash → Imagen 3.0 auto-fallback")
    print("─" * 62)

    auto_adapter = GeminiImageAdapter()
    img3_adapter = Imagen3Adapter()

    rounds = [
        ("赛博朋克城市夜景，霓虹灯倒影，电影感光效，16:9",    "16:9", auto_adapter, "Round 1 — Gemini Flash"),
        ("古风仙侠女子，白衣飘飘，竹林晨雾，16:9",            "16:9", auto_adapter, "Round 2 — Gemini Flash"),
        ("极简主义抽象艺术，黑白几何线条，正方形构图",          "1:1",  auto_adapter, "Round 3 — Gemini Flash (1:1)"),
        ("电影级写实风景，夕阳下的草原，超高清，8K质感",        "16:9", img3_adapter, "Round 4 — Imagen 3.0 direct"),
    ]

    last_result = None
    for prompt, aspect, adapter, label in rounds:
        req = GenerateRequest(prompt=prompt, params={"aspect_ratio": aspect})
        r = await run_case(label, adapter.generate(req))
        if r:
            last_result = r

    return last_result


# ── text → video ───────────────────────────────────────────────────────────────
async def test_text2video():
    print("\n" + "─" * 62)
    print("🎬  TEXT → VIDEO  (Veo 3.1 / 3.1 Fast / 3.0 / 2.0)")
    print("─" * 62)

    rounds = [
        # (prompt, dur, aspect, adapter_key, label)
        ("城市夜景空镜，街灯倒映水面，镜头缓慢上移，电影感", 4, "16:9", "veo-3.1",      "Round 1 — Veo 3.1        4s"),
        ("海边日落，波浪拍打礁石，慢动作特写",               6, "16:9", "veo-3.1-fast", "Round 2 — Veo 3.1 Fast   6s"),
        ("古镇夜市，人群熙攘，航拍俯视，暖色调",             8, "9:16", "veo-3.0",      "Round 3 — Veo 3.0        8s 9:16"),
        ("城市延时摄影，车流如河，蓝色冷调，俯拍",           8, "16:9", "veo-2.0",      "Round 4 — Veo 2.0 GA     8s"),
    ]

    adapter_map = {
        "veo-3.1":      Veo31Adapter(),
        "veo-3.1-fast": Veo31FastAdapter(),
        "veo-3.0":      Veo30Adapter(),
        "veo-2.0":      Veo20Adapter(),
    }

    for prompt, dur, aspect, key, label in rounds:
        adapter = adapter_map[key]
        req = GenerateRequest(prompt=prompt, params={"duration": dur, "aspect_ratio": aspect})
        await run_case(label, adapter.generate(req))


# ── image → video ──────────────────────────────────────────────────────────────
async def test_img2video(image_path: str):
    print("\n" + "─" * 62)
    print("🖼️→🎬  IMAGE → VIDEO  (Veo img2vid)")
    print("─" * 62)

    # Read the local PNG file and encode as base64
    # (adapter expects http URL or raw base64 string, not a file path)
    with open(image_path, "rb") as f:
        img_b64 = base64.b64encode(f.read()).decode()

    adapter = VeoAdapter()
    rounds = [
        ("画面缓慢推进，由静变动，镜头轻微呼吸感，电影级", 4, "Round 1 — img2vid  4s (Veo 3.1)"),
        ("主体轻微摆动，环境光随风变换，超现实氛围",        8, "Round 2 — img2vid  8s"),
    ]

    for prompt, dur, label in rounds:
        req = GenerateRequest(
            prompt=prompt,
            params={"duration": dur, "aspect_ratio": "16:9"},
            reference_images=[img_b64],  # pass as base64 string
        )
        await run_case(label, adapter.generate(req))


# ── main ───────────────────────────────────────────────────────────────────────
async def main():
    print("=" * 62)
    print("  AIMV — Google API Integration Tests")
    print("  Project : qy-shoplazza-02")
    print("  SA      : ai-compet-huangshaozheng@qy-shoplazza-02.iam.gserviceaccount.com")
    print(f"  Outputs : {SAVE_DIR}")
    print("=" * 62)

    # 1. Unit test (no API call)
    test_duration_clamp()

    # 2. Image generation (4 rounds)
    last_image = await test_image()

    # 3. Text → Video (4 rounds)
    await test_text2video()

    # 4. Image → Video (uses last generated image)
    if last_image and last_image.file_url:
        await test_img2video(last_image.file_url)
    else:
        print(f"\n{WARN}  Skipping img2video — no image available")

    # ── summary ────────────────────────────────────────────────────────────────
    print("\n" + "=" * 62)
    print("  SUMMARY")
    print("=" * 62)
    n_pass = sum(1 for r in results if r["ok"])
    n_fail = sum(1 for r in results if not r["ok"])
    total_s = sum(r["elapsed"] for r in results)
    print(f"  Cases  : {len(results)}   {PASS} {n_pass}   {FAIL} {n_fail}   ⏱ {total_s:.0f}s total")

    if n_fail:
        print("\n  Failed:")
        for r in results:
            if not r["ok"]:
                print(f"    {FAIL}  {r['label']}")
                print(f"         {r.get('error','')[:120]}")

    print(f"\n  Local files saved ({len(_saved)}):")
    for s in _saved:
        print(f"    {s['path']}  ({s['size_kb']} KB)")

    print()
    sys.exit(0 if n_fail == 0 else 1)


if __name__ == "__main__":
    asyncio.run(main())
