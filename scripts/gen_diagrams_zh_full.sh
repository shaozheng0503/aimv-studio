#!/bin/bash
# 剩余 9 张中文版配图
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
           \"n\": 1}" -o "/tmp/zhf_${name}.json"
    if jq -e '.data[0].b64_json' "/tmp/zhf_${name}.json" > /dev/null 2>&1; then
      jq -r '.data[0].b64_json' "/tmp/zhf_${name}.json" | base64 --decode > "$f"
      echo "  OK ($(stat -f%z "$f") bytes)"
      sleep 12
      return 0
    else
      err=$(jq -r '.error.code // empty' "/tmp/zhf_${name}.json" 2>/dev/null)
      echo "  FAIL: $err — sleep $((try*20))s"
      sleep $((try*20))
    fi
  done
  return 1
}

# 已经生成的 3 张（脚本会自动 skip）
gen "fig2_1_architecture" "skip"
gen "fig3_2_agent_team" "skip"
gen "fig3_4_verifier" "skip"

# 剩余 9 张中文版

gen "fig3_3_router" \
  "Modern flat infographic with SIMPLIFIED CHINESE labels showing AI model routing logic: a central router robot labeled \"路由器\" with cables connecting to 4 AI model boxes on the right labeled \"Veo\", \"Seedance\", \"Grok\", \"Wan2.2\". Left side shows 5 shot type icons with Chinese labels: \"风景镜头\", \"动作镜头\", \"人像镜头\", \"产品镜头\", \"风格化镜头\". Below shows a fallback safety net labeled \"模型回退\". Clean isometric style, pastel colors, white background, dribbble quality. Chinese characters must be clearly readable."

gen "ch3_cover_pipeline" \
  "Isometric infographic with SIMPLIFIED CHINESE title \"AI 音乐视频生成流水线\". Shows an AI music video generation pipeline as a flowing creative river from left to right: a lightbulb (idea) on the left, flowing through several glowing nodes with Chinese labels: \"创意\", \"音乐分析\", \"智能体协作\", \"画面生成\", \"成片\", ending with a screen showing the final music video on the right. Each stage glows with different color, connected by flowing energy streams. Modern flat illustration, pastel and neon accents, white background, magazine cover quality. Chinese characters clearly readable."

gen "fig5_1_state_machine" \
  "Modern flat infographic with SIMPLIFIED CHINESE labels showing a project lifecycle as a journey map with 5 circular waypoint nodes connected by a winding road, each labeled in Chinese: \"草稿\" (sketch pad icon), \"规划中\" (gears icon), \"已规划\" (checkmark icon), \"生成中\" (film reel icon), \"完成\" (trophy icon). One detour branch leads to a failure node labeled \"失败\" with restart arrow labeled \"重试\". Soft pastel gradient road, isometric perspective, white background, dribbble quality. Chinese clearly rendered."

gen "fig5_3_er_diagram" \
  "Clean flat database entity relationship diagram in modern infographic style with SIMPLIFIED CHINESE entity titles, 5 rounded rectangle entity boxes labeled in Chinese: \"用户表\" (User), \"项目表\" (Project), \"任务表\" (Task), \"媒体表\" (Media), \"点赞表\" (GalleryLike), connected by labeled foreign key arrows showing one-to-many relations (with Chinese text \"一对多\"). Each entity box has rows of field names. Soft pastel colors per entity, white background, professional dribbble quality. Chinese characters clearly rendered."

gen "fig6_3_celery_chord" \
  "Modern flat infographic with SIMPLIFIED CHINESE labels and title \"异步任务依赖图\". Shows an asynchronous task dependency graph: two parallel task lanes on the left labeled \"图像生成\" and \"音乐生成\" converging into a central fan-in node labeled \"汇聚点\", then flowing into a sequential chain of 4 numbered video tasks labeled \"视频 1\" \"视频 2\" \"视频 3\" \"视频 4\", ending in a composer node labeled \"合成\". Glowing flow arrows, color-coded task boxes, isometric perspective, pastel palette, white background, dribbble quality. Chinese clearly readable."

gen "fig7_2_metrics" \
  "Modern academic infographic with SIMPLIFIED CHINESE title \"系统性能指标\" showing two side-by-side data visualizations: left side a clean donut pie chart titled \"流水线时延分解\" with 5-6 colored segments having Chinese labels like \"视频生成\", \"图像并发\", \"音乐生成\", \"合成\", \"规划\". Right side a clean bar chart titled \"用户研究 MOS 评分\" with 4 bars labeled in Chinese: \"视觉\", \"剧情\", \"节奏\", \"满意度\". Soft pastel palette, gridded background, white canvas, professional academic infographic. Chinese clearly rendered."

gen "fig7_3_eval_distribution" \
  "Clean flat infographic with SIMPLIFIED CHINESE title \"评测集风格分布\" showing 7 cute music video genre icons arranged in a circular pie chart, each slice with a Chinese label: \"韩娱练习生\" microphone icon, \"国风古典\" hanfu icon, \"赛博朋克\" neon city icon, \"复古迪斯科\" mirror ball icon, \"独立电影\" camera icon, \"都市甜酷\" street icon, \"幻想童话\" castle icon. Each slice in distinct pastel color. Modern flat vector style, white background, dribbble quality. Chinese characters clearly rendered."

gen "ch2_cover_techstack" \
  "Beautiful isometric chapter cover illustration with a SIMPLIFIED CHINESE title \"开发环境与相关技术\" floating at top. Below shows a magical technology stack tower rising from clouds, each floor a different tech layer glowing with icons: web browser, server, gears, brain, database. Soft pastel sky background, dreamy and inviting, flat illustration style, dribbble cover quality. Chinese title clearly readable."

gen "ch6_cover_workshop" \
  "A flat illustration with SIMPLIFIED CHINESE title \"系统设计与实现\" floating at top. Below shows a young creator at a desk with a glowing laptop displaying a music video editing interface (with small Chinese UI text like \"分镜\" \"导出\" visible). Surrounded by floating UI elements like timelines, AI suggestion bubbles, video thumbnails. Cozy creative workspace, soft warm lighting, modern flat vector style, pastel palette, dribbble cover quality. Chinese title clearly readable."

echo "ALL DONE."
ls -la "$OUT"
