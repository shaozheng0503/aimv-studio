#!/bin/bash
# v2: medium quality + 简化 prompt + 更短超时
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
    curl --max-time 180 -s -X POST "$ENDPOINT" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $AZURE_API_KEY" \
      -d "{\"prompt\": $(jq -Rn --arg p "$prompt" '$p'),
           \"size\": \"1024x1024\",
           \"quality\": \"medium\",
           \"output_compression\": 100,
           \"output_format\": \"png\",
           \"n\": 1}" -o "/tmp/d2_${name}.json"
    if jq -e '.data[0].b64_json' "/tmp/d2_${name}.json" > /dev/null 2>&1; then
      jq -r '.data[0].b64_json' "/tmp/d2_${name}.json" | base64 --decode > "$f"
      echo "  OK ($(stat -f%z "$f") bytes)"
      sleep 15
      return 0
    else
      err=$(jq -r '.error.code // empty' "/tmp/d2_${name}.json" 2>/dev/null)
      echo "  FAIL: $err — sleep $((try*20))s"
      sleep $((try*20))
    fi
  done
  return 1
}

# 3 张试验图（每张 prompt 控制在 300 字符内，更稳定）

gen "fig2_1_architecture" \
  "Isometric infographic, 5-layer technology stack architecture cake from top to bottom: Frontend Vue.js, API FastAPI, Async Workers Celery Redis, AI Agents brain icons, Database PostgreSQL. Each layer translucent colored slab connected by glowing data flow lines. Modern flat vector style, soft pastel colors, white background, clean professional tech diagram, dribbble quality, minimal text."

gen "fig3_2_agent_team" \
  "Flat illustration of four cute AI agents collaborating on a music video, arranged around a central glowing screen showing a film reel: Screenwriter with script pen, Director with clapperboard, Music Producer with headphones, Verifier with magnifying glass. Distinct colors blue green purple red, soft gradient connection arrows flowing between them. Modern flat vector style, pastel palette, white background, dribbble quality, professional friendly, minimal text."

gen "ch3_cover_pipeline" \
  "Isometric infographic of an AI music video generation pipeline as a flowing creative river: lightbulb idea on the left flows through music wave analysis, four AI agent characters, a magic film generator, ending with a screen showing the final music video on the right. Each stage glows with different colors connected by flowing energy streams. Modern flat illustration, pastel and neon accents, white background, magazine cover quality, no text."

echo "DONE."
ls -la "$OUT"
