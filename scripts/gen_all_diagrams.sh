#!/bin/bash
# 全量生成论文所有 GPT-image-2 配图（含已生成的可跳过）
set -u
export AZURE_API_KEY="${AZURE_API_KEY:?set AZURE_API_KEY in your environment}"
ENDPOINT="https://shopai3674eastus2.cognitiveservices.azure.com/openai/deployments/gpt-image-2-algo-ai-gen-store-01/images/generations?api-version=2024-02-01"
OUT="docs/figures_generated/ai_diagrams"
mkdir -p "$OUT"

gen() {
  local name="$1"; local prompt="$2"
  local f="$OUT/${name}.png"
  if [ -f "$f" ] && [ "$(stat -f%z "$f" 2>/dev/null || echo 0)" -gt 50000 ]; then
    echo "[skip] $name (exists)"
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
           \"n\": 1}" -o "/tmp/all_${name}.json"
    if jq -e '.data[0].b64_json' "/tmp/all_${name}.json" > /dev/null 2>&1; then
      jq -r '.data[0].b64_json' "/tmp/all_${name}.json" | base64 --decode > "$f"
      echo "  OK ($(stat -f%z "$f") bytes)"
      sleep 12
      return 0
    else
      err=$(jq -r '.error.code // empty' "/tmp/all_${name}.json" 2>/dev/null)
      echo "  FAIL: $err — sleep $((try*20))s"
      sleep $((try*20))
    fi
  done
  return 1
}

# === 已经在跑的（试验图） ===
gen "fig2_1_architecture" \
  "Isometric infographic, 5-layer technology stack architecture cake from top to bottom: Frontend Vue.js, API FastAPI, Async Workers Celery Redis, AI Agents brain icons, Database PostgreSQL. Each layer translucent colored slab connected by glowing data flow lines. Modern flat vector style, soft pastel colors, white background, clean professional tech diagram, dribbble quality, minimal text."

gen "fig3_2_agent_team" \
  "Flat illustration of four cute AI agents collaborating on a music video, arranged around a central glowing screen showing a film reel: Screenwriter with script pen, Director with clapperboard, Music Producer with headphones, Verifier with magnifying glass. Distinct colors blue green purple red, soft gradient connection arrows flowing between them. Modern flat vector style, pastel palette, white background, dribbble quality, professional friendly, minimal text."

gen "ch3_cover_pipeline" \
  "Isometric infographic of an AI music video generation pipeline as a flowing creative river: lightbulb idea on the left flows through music wave analysis, four AI agent characters, a magic film generator, ending with a screen showing the final music video on the right. Each stage glows with different colors connected by flowing energy streams. Modern flat illustration, pastel and neon accents, white background, magazine cover quality, no text."

# === 全量增量 ===

gen "fig3_3_router" \
  "Modern flat infographic showing AI model routing logic: a central router robot with cables connecting to multiple AI model boxes labeled Veo, Seedance, Grok, Wan2.2. The router has decision branches glowing in different colors based on shot type. Below shows a fallback safety net catching falls. Clean isometric style, pastel colors, white background, dribbble quality, minimal English labels only."

gen "fig3_4_verifier" \
  "Flat illustration of an AI quality verifier robot examining a generated video frame with three glowing checkmark badges floating above: a star (visual), a person (consistency), a target (adherence). A circular retry loop arrow wraps around the verifier with 4 stages glowing in escalating colors green yellow orange red. Modern flat vector, pastel palette, white background, dribbble quality, minimal labels."

gen "fig5_1_state_machine" \
  "Modern flat infographic showing a project lifecycle as a journey map with 5 circular waypoint nodes connected by a winding road: draft (sketch pad), planning (gears), planned (checkmark), generating (film reel), done (trophy). One detour branch leads to a failure node with restart arrow. Soft pastel gradient road, isometric perspective, white background, dribbble quality, minimal labels."

gen "fig5_3_er_diagram" \
  "Clean flat database entity relationship diagram in modern infographic style, 5 rounded rectangle entity boxes labeled User Project Task Media GalleryLike, connected by labeled foreign key arrows showing one-to-many relations. Each entity box has rows of field names. Soft pastel colors per entity, white background, professional dribbble quality, suitable for thesis figure."

gen "fig6_3_celery_chord" \
  "Modern flat infographic showing an asynchronous task dependency graph: two parallel task lanes (Image generation and Music generation) converging into a fan-in chord point, then flowing into a sequential video chain of 4 numbered video tasks, ending in a composer node. Glowing flow arrows, color-coded task boxes, isometric perspective, pastel palette, white background, dribbble quality, minimal English labels."

gen "fig7_2_metrics" \
  "Modern infographic showing two side-by-side data visualizations on a thesis figure layout: left side a clean donut pie chart with 5-6 colored segments showing time breakdown percentages, right side a clean bar chart with 4 bars of different heights and error whiskers. Soft pastel palette, gridded background, white canvas, professional academic infographic quality."

gen "fig7_3_eval_distribution" \
  "Clean flat infographic showing 7 cute music video genre icons arranged in a circular distribution pie chart: K-pop microphone, Chinese hanfu, cyberpunk neon, disco mirror ball, indie film camera, urban street, fantasy castle. Each genre slice in distinct pastel color with small number label. Modern flat vector style, white background, dribbble quality."

gen "ch2_cover_techstack" \
  "Beautiful isometric chapter cover illustration showing a magical technology stack tower rising from clouds, each floor a different tech layer glowing with icons: web browser, server, gears, brain, database. Soft pastel sky background, dreamy and inviting, flat illustration style, dribbble cover quality, no text."

gen "ch6_cover_workshop" \
  "A flat illustration of a young creator at a desk with a glowing laptop displaying a music video editing interface, surrounded by floating UI elements like timelines, AI suggestion bubbles, video thumbnails. Cozy creative workspace, soft warm lighting, modern flat vector style, pastel palette, dribbble cover quality, no text."

echo "ALL DONE."
ls -la "$OUT"
