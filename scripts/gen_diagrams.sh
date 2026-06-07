#!/bin/bash
# 用 GPT-image-2 生成论文配图（章首封面 + 系统架构示意）
# 间隔 30s 避免限流
set -u
export AZURE_API_KEY="${AZURE_API_KEY:?set AZURE_API_KEY in your environment}"
ENDPOINT="https://shopai3674eastus2.cognitiveservices.azure.com/openai/deployments/gpt-image-2-algo-ai-gen-store-01/images/generations?api-version=2024-02-01"
OUT="docs/figures_generated/ai_diagrams"
mkdir -p "$OUT"

gen() {
  local name="$1"; local prompt="$2"
  local f="$OUT/${name}.png"
  if [ -f "$f" ] && [ "$(stat -f%z "$f" 2>/dev/null || echo 0)" -gt 50000 ]; then
    echo "[skip] $name"
    return 0
  fi
  for try in 1 2 3 4; do
    echo "[gen $try/4] $name"
    curl -s -X POST "$ENDPOINT" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $AZURE_API_KEY" \
      -d "{\"prompt\": $(jq -Rn --arg p "$prompt" '$p'),
           \"size\": \"1024x1024\",
           \"quality\": \"high\",
           \"output_compression\": 100,
           \"output_format\": \"png\",
           \"n\": 1}" -o "/tmp/d_${name}.json"
    if jq -e '.data[0].b64_json' "/tmp/d_${name}.json" > /dev/null 2>&1; then
      jq -r '.data[0].b64_json' "/tmp/d_${name}.json" | base64 --decode > "$f"
      echo "  OK ($(stat -f%z "$f") bytes)"
      sleep 30
      return 0
    else
      err=$(jq -r '.error.code // empty' "/tmp/d_${name}.json" 2>/dev/null)
      echo "  FAIL: $err — sleep $((try*40))s"
      sleep $((try*40))
    fi
  done
  return 1
}

# ============= 试验 3 张 =============

# 1) 图 2.1 - 五层架构鸟瞰（技术感强）
gen "fig2_1_architecture" \
  "A clean modern isometric infographic showing a 5-layer technology stack architecture for a web application, layered like a 3D tiered cake from top to bottom: Layer 1 Frontend (Vue.js + Element Plus icons), Layer 2 API (FastAPI rocket icon), Layer 3 Async Workers (Celery + Redis + RabbitMQ icons), Layer 4 AI Agents and Adapters (brain icon with neural network), Layer 5 Data Storage (PostgreSQL + MinIO database icons). Each layer is a translucent colored slab connected by data flow lines. Professional tech diagram style, soft pastel colors, white background, flat vector illustration with subtle shadows, ultra clean composition, suitable for academic thesis figure. NO text labels needed, focus on icons and structural clarity."

# 2) 图 3.2 - 四个 Agent 协作（拟人化概念图）
gen "fig3_2_agent_team" \
  "A clean flat illustration showing four cute animated AI agents collaborating on a music video project, arranged in a circle around a central glowing screen showing a music video reel. The four agents are: a Screenwriter agent with a script and pen, a Director agent with a clapperboard, a Music Producer agent with headphones and notes, and a Verifier agent with a magnifying glass and checkmark. Each agent has a distinct color (blue, green, purple, red). Soft gradient connection lines flow between them. Modern flat vector style, pastel palette, white background, dribbble-quality illustration, professional and friendly, suitable for academic thesis. Minimal text."

# 3) 章 3 章首封面 - 整个 MV 自动生成流程意境图
gen "ch3_cover_pipeline" \
  "A beautiful isometric infographic showing an end-to-end AI music video generation pipeline as a flowing river of creativity: starting from a lightbulb (idea) on the left, flowing through several glowing nodes representing music analysis, AI agents collaboration, visual generation, and ending with a film reel and screens showing the final MV on the right. Each stage glows with a different color, connected by flowing energy streams. Modern flat illustration style, pastel + neon accents, white background, magazine-cover quality, suitable for thesis chapter cover."

echo "DONE."
ls -la "$OUT"
