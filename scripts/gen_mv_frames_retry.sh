#!/bin/bash
# 批量生成 MV 示例帧 - 带重试和间隔，跳过已生成
set -u
export AZURE_API_KEY="${AZURE_API_KEY:?set AZURE_API_KEY in your environment}"
ENDPOINT="https://shopai3674eastus2.cognitiveservices.azure.com/openai/deployments/gpt-image-2-algo-ai-gen-store-01/images/generations?api-version=2024-02-01"
OUT_DIR="docs/figures_generated/mv_frames"
mkdir -p "$OUT_DIR"
MAX_RETRY=5
INTER_GAP=8   # 每张之间间隔(秒) - 避免触发限流

gen() {
  local name="$1"; local prompt="$2"
  local out="$OUT_DIR/${name}.png"
  if [ -f "$out" ] && [ "$(stat -f%z "$out" 2>/dev/null || echo 0)" -gt 50000 ]; then
    echo "[skip] $name (already exists, $(stat -f%z "$out") bytes)"
    return 0
  fi
  for try in $(seq 1 $MAX_RETRY); do
    echo "[gen $try/$MAX_RETRY] $name"
    curl -s -X POST "$ENDPOINT" \
      -H "Content-Type: application/json" \
      -H "Authorization: Bearer $AZURE_API_KEY" \
      -d "{
         \"prompt\": $(jq -Rn --arg p "$prompt" '$p'),
         \"size\": \"1024x1024\",
         \"quality\": \"medium\",
         \"output_compression\": 100,
         \"output_format\": \"png\",
         \"n\": 1
        }" -o "/tmp/gen_${name}.json"
    if jq -e '.data[0].b64_json' "/tmp/gen_${name}.json" > /dev/null 2>&1; then
      jq -r '.data[0].b64_json' "/tmp/gen_${name}.json" | base64 --decode > "$out"
      echo "  OK ($(stat -f%z "$out") bytes)"
      sleep $INTER_GAP
      return 0
    else
      ERR=$(jq -r '.error.code // empty' "/tmp/gen_${name}.json" 2>/dev/null)
      echo "  FAIL: $ERR — sleeping $((try*15))s before retry"
      sleep $((try*15))
    fi
  done
  echo "  GIVE UP after $MAX_RETRY retries"
  return 1
}

# 第 1 组：国风古典
gen "guofeng_01_overlook" \
  "A cinematic music video still: a young Chinese woman in flowing pale-pink Hanfu dress with golden silk belt, long jet-black hair, standing on a misty mountain peak at sunrise overlooking a sea of clouds, soft warm rim light, ethereal dreamy atmosphere, shallow depth of field, ultra realistic photography"
gen "guofeng_02_peach" \
  "A cinematic music video still: the SAME young Chinese woman in flowing pale-pink Hanfu dress with golden silk belt, long jet-black hair, dancing gracefully in a blooming peach blossom forest, petals falling around her, soft daylight filtering through trees, medium shot, motion-aware composition, ultra realistic photography"
gen "guofeng_03_singing" \
  "A cinematic music video close-up: the SAME young Chinese woman in pale-pink Hanfu dress, close-up portrait shot, eyes closed singing emotionally, single tear glistening on her cheek, soft golden rim light from left side, blurred peach blossom bokeh background, cinematic 3-point lighting, ultra realistic photography"
gen "guofeng_04_dusk" \
  "A cinematic music video still: the SAME young Chinese woman in pale-pink Hanfu dress, standing alone on a stone bridge at dusk, distant pagoda silhouette behind her, warm orange sunset sky, long shadow, wide cinematic shot, melancholic mood, ultra realistic photography"

# 第 2 组：赛博朋克
gen "cyber_01_neon" \
  "A cinematic cyberpunk music video still: a stylish young woman in a black leather jacket with neon-purple accents and cyan undercut hair, standing in a rain-soaked Tokyo street at night, drenched in pink and cyan neon signs reflections, wide shot, anamorphic lens flares, ultra detailed"
gen "cyber_02_close" \
  "A cinematic cyberpunk music video close-up: the SAME young woman in black leather jacket with neon-purple accents, cyan undercut hair, intense close-up portrait, neon pink and cyan light reflections on her face, slight rain droplets on cheek, looking at camera defiantly, shallow depth of field, ultra detailed"
gen "cyber_03_rooftop" \
  "A cinematic cyberpunk music video still: the SAME young woman in black leather jacket, cyan undercut hair, standing on a rooftop overlooking a futuristic megacity skyline at night, holographic ads floating above buildings, flying cars in distance, wide cinematic shot, ultra detailed"
gen "cyber_04_run" \
  "A cinematic cyberpunk music video still: the SAME young woman in black leather jacket, cyan undercut hair, running through a narrow alley with neon signs in Chinese and Japanese, motion blur, dramatic backlight from oncoming flying car, dynamic action shot, ultra detailed"

# 第 3 组：复古迪斯科
gen "disco_01_dance" \
  "A vibrant retro disco music video still: a stylish young woman in a glittery silver sequined dress with feather boa, big curly hair, dancing under a sparkling mirror ball, 1970s discotheque, warm amber and magenta stage lighting, lens flares, full body shot, film grain texture"
gen "disco_02_close" \
  "A vibrant retro disco music video close-up: the SAME young woman in silver sequined dress, big curly hair, big golden hoop earrings, close-up portrait singing into a vintage microphone, warm magenta and amber spotlight, sparkles reflecting on her cheek, film grain texture"
gen "disco_03_crowd" \
  "A vibrant retro disco music video still: the SAME young woman in silver sequined dress, dancing in the center of a crowded 1970s disco floor, surrounded by other dancers, mirror ball reflections, warm lighting, wide cinematic shot, film grain texture"
gen "disco_04_outside" \
  "A vibrant retro disco music video still: the SAME young woman in silver sequined dress, walking out of a neon-lit disco club at night, wet pavement reflections, vintage car parked beside, 1970s street vibe, medium shot, film grain texture"

echo "ALL DONE."
ls -la "$OUT_DIR"
