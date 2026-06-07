#!/bin/bash
# 中文版配图 - prompt 明确指定 Simplified Chinese 字符
# 先清空目录中的英文图（已经备份到 ai_diagrams_en/），再重新生成
set -u
export AZURE_API_KEY="${AZURE_API_KEY:?set AZURE_API_KEY in your environment}"
ENDPOINT="https://shopai3674eastus2.cognitiveservices.azure.com/openai/deployments/gpt-image-2-algo-ai-gen-store-01/images/generations?api-version=2024-02-01"
OUT="docs/figures_generated/ai_diagrams"
# 先清空 ai_diagrams 让所有图重新生成
rm -f "$OUT"/*.png

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
           \"n\": 1}" -o "/tmp/zh_${name}.json"
    if jq -e '.data[0].b64_json' "/tmp/zh_${name}.json" > /dev/null 2>&1; then
      jq -r '.data[0].b64_json' "/tmp/zh_${name}.json" | base64 --decode > "$f"
      echo "  OK ($(stat -f%z "$f") bytes)"
      sleep 15
      return 0
    else
      err=$(jq -r '.error.code // empty' "/tmp/zh_${name}.json" 2>/dev/null)
      echo "  FAIL: $err — sleep $((try*20))s"
      sleep $((try*20))
    fi
  done
  return 1
}

# 先试 3 张代表性的看中文渲染效果

# 1) 图 2.1 五层架构（关键中文标签：前端 / API / 异步 / AI / 数据库）
gen "fig2_1_architecture" \
  "Isometric infographic with SIMPLIFIED CHINESE labels, 5-layer technology stack architecture cake from top to bottom. Each translucent colored slab has clear Chinese label characters: top layer labeled \"前端\" with Vue.js icon, second labeled \"API\" with FastAPI rocket icon, third labeled \"异步\" with Celery and Redis icons, fourth labeled \"AI 智能体\" with brain icon, bottom labeled \"数据库\" with PostgreSQL icon. Modern flat vector style, soft pastel colors, white background, clean professional tech diagram, dribbble quality. Chinese characters must be clearly rendered and readable."

# 2) 图 3.2 多 Agent 协作（关键中文标签：编剧 / 导演 / 音乐人 / 质检员）
gen "fig3_2_agent_team" \
  "Flat illustration with SIMPLIFIED CHINESE labels, of four cute AI agents collaborating on a music video, arranged around a central glowing screen showing a film reel. Each agent has a clear Chinese name label below: top-left labeled \"编剧\" with script and pen, top-right labeled \"导演\" with clapperboard, bottom-left labeled \"音乐人\" with headphones and notes, bottom-right labeled \"质检员\" with magnifying glass. Distinct colors blue green purple red, soft gradient connection arrows. Modern flat vector style, pastel palette, white background, dribbble quality. Chinese characters must be rendered correctly and readable."

# 3) 图 3.4 Verifier（关键中文标签：视觉质量 / 一致性 / 契合度 / 分析-评估-改进-重试）
gen "fig3_4_verifier" \
  "Flat illustration with SIMPLIFIED CHINESE labels of an AI quality verifier robot examining a generated video frame. Three glowing checkmark badges floating above with Chinese labels: \"视觉质量\" (star icon), \"角色一致\" (person icon), \"提示契合\" (target icon). A circular retry loop arrow wraps around the verifier with 4 stages with Chinese labels: \"分析\", \"评估\", \"改进\", \"重试\". Modern flat vector, pastel palette, white background, dribbble quality. Chinese characters clearly rendered."

echo "DONE first 3."
ls -la "$OUT"
