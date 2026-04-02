# AIMV 分镜 Agent 链路全解析

> 从用户的一句话，到音乐、场景、模特、最终 MV 的完整数据流。

---

## 一、总体架构图

```
用户输入："帮我做一个关于孤独旅人在星空下徒步的MV，风格史诗感，配乐大气磅礴"
                          │
                          ▼
              ┌───────────────────────┐
              │  0. 前置：音乐分析     │  librosa + htdemucs + faster-whisper
              │  MusicAnalyzer        │  → BPM / sections / 歌词 / 能量曲线
              └──────────┬────────────┘
                         │  music_analysis dict
                         ▼
              ┌───────────────────────┐
              │  Planning Crew        │  CrewAI sequential · Qwen3.5-9B
              │  (三 Agent 串行)       │
              │                       │
              │  Agent 1 Screenwriter │  → character_bank + storyboard（叙事）
              │      ↓ context        │
              │  Agent 2 Director     │  → image/video prompt + 摄影指令
              │      ↓ context        │
              │  Agent 3 Music        │  → music_plan（结构/同步点）
              │         Producer      │
              └──────────┬────────────┘
                         │  plan dict（合并后）
                         ▼
              ┌───────────────────────┐
              │  POST /pipeline/start │  存库 → 触发 Celery
              └──────────┬────────────┘
                         │
          ┌──────────────▼──────────────┐
          │  Phase 1（Celery chord）     │  并行
          │  · 每分镜 → 生成图片         │  Z-Image adapter
          │  · 整首 → 生成音乐           │  ACEStep / Suno / Lyria
          └──────────┬──────────────────┘
                     │ chord callback（全部完成后自动触发）
                     ▼
          ┌──────────────────────────────┐
          │  Phase 2（sequential）        │  ShotRouter 按帧链接
          │  · sing 镜头 → Seedance/Wan  │  逐个生成视频
          │  · story 镜头 → Veo/Grok     │  上一帧 = 下一帧起始
          └──────────┬───────────────────┘
                     │ .delay()
                     ▼
          ┌──────────────────────────────┐
          │  Phase 3 Compose             │  FFmpeg
          │  concat 视频 + merge 音频     │  → 最终 MV（-14 LUFS 标准化）
          └──────────────────────────────┘
                     │ WebSocket 推送进度
                     ▼
              前端实时预览 ✓
```

---

## 二、第 0 步：音乐分析（可选前置）

**触发条件**：用户上传了音频文件，或系统先生成了参考音乐。

### 处理内容

| 分析项 | 工具 | 输出 |
|---|---|---|
| BPM + 节拍时间戳 | librosa beat_track | `bpm: 87.5`, `beats: [{time: 0.34, strength: 0.9}, ...]` |
| 段落结构 | MFCC+Chroma 相似度矩阵 + 聚类 | `sections: [intro/verse/chorus/bridge/outro]` |
| 人声分离 | htdemucs（two-stems） | `vocal.wav` + `no_vocals.wav` |
| 歌词识别 | faster-whisper base | `lyrics: [{text: "...", start: 12.3, end: 14.8}]` |
| 能量曲线 | 逐秒 RMS | `energy_curve: [0.12, 0.45, 0.89, ...]`（归一化 0-1） |

### 实际输出示例

```json
{
  "bpm": 87.5,
  "duration": 180.0,
  "sections": [
    {"label": "intro",  "start": 0.0,   "end": 18.2,  "energy": 0.23},
    {"label": "verse",  "start": 18.2,  "end": 54.6,  "energy": 0.41},
    {"label": "chorus", "start": 54.6,  "end": 90.0,  "energy": 0.87},
    {"label": "bridge", "start": 90.0,  "end": 120.0, "energy": 0.31},
    {"label": "outro",  "start": 150.0, "end": 180.0, "energy": 0.18}
  ],
  "energy_curve": [0.12, 0.18, 0.23, 0.31, ...],
  "lyrics": []
}
```

**作用**：这个 dict 直接注入 Agent 1 的 task description，让分镜时间轴与真实音乐结构对齐。

---

## 三、Agent 1 — Screenwriter（叙事拆分）

### 职责

读懂用户一句话意图 → 拆分角色库 → 规划叙事分镜段落。

### 输入（注入到 task description）

```
## User Creative Intent
帮我做一个关于孤独旅人在星空下徒步的MV，风格史诗感，配乐大气磅礴

## Music Analysis
BPM: 87.5   Duration: 180.0s
Sections: [intro@0-18s, verse@18-54s, chorus@54-90s, bridge@90-120s, outro@150-180s]
Lyrics: []
Energy curve: [0.12, 0.18, 0.23 ...]

## Style Preferences
Visual style: 独立电影   Music style: auto   Mood: epic
```

### 输出结构

```json
{
  "character_bank": { "<key>": { ...角色档案... } },
  "storyboard":    [ { ...分镜段落... } ]
}
```

### 实际输出（孤独旅人MV，共 6 个分镜）

**character_bank — 角色库（全片唯一定义）**

```json
{
  "The_Wanderer": {
    "name": "The Wanderer",
    "age_range": "25-30",
    "gender": "Androgynous",
    "appearance": "Weathered face, deep-set eyes reflecting starlight, short tousled hair, slight stubble.",
    "outfit": "Worn leather jacket, dark grey trousers, heavy boots, carrying an old brass lantern.",
    "style_tags": ["Indie Film", "Cinematic", "Solitary", "Ethereal", "Weathered"],
    "role": "Protagonist",
    "personality": "Resilient, introspective, seeking connection amidst isolation."
  }
}
```

> 角色档案包含：外貌细节 + 服装 + 风格标签 + 性格。后续 Agent 2 在生成每个分镜的 image_prompt 时，会把这段描述**直接内联进 prompt**，保证全片角色视觉一致性，不依赖模型的"记忆"。

**storyboard — 叙事分镜（6 段）**

| segment_id | label | 时间 | 情绪 | 内容摘要 |
|---|---|---|---|---|
| 1 | story | 0–15s | Mysterious | 荒野远景，星云天空，远处一盏灯笼 |
| 2 | story | 15–45s | Melancholic | 旅人特写，手持摄像机抖动，仰望星空 |
| 3 | story | 45–60s | Determined | 旅人艰难爬上山脊，轮廓映衬星海 |
| 4 | **sing** | 60–90s | Intimate | 旅人在岩洞里面向镜头演唱，灯笼照亮脸庞 |
| 5 | story | 90–120s | Nostalgic | 记忆蒙太奇：手、地图、剪影 |
| 6 | story | 150–180s | Transcendent | 旅人走向悬崖边缘，俯视星空，灯笼放飞 |

```json
{
  "segment_id": 4,
  "label": "sing",
  "start_time": 60.0,
  "end_time": 90.0,
  "description": "The Wanderer sings directly to camera in a dimly lit cave. The lantern illuminates their face. Emotional, raw vocal performance.",
  "mood": "Intimate",
  "characters": ["The_Wanderer"]
}
```

**关键设计**
- `label: "sing"` — 标记演唱镜头，后续 ShotRouter 会路由到 Seedance/Wan（擅长人物面向镜头+口型）
- `label: "story"` — 叙事场景，路由到 Veo/Grok（擅长电影质感）
- `start_time / end_time` 与 music sections 对齐（intro→第1段，chorus→第4段演唱）
- `characters: []` 空数组 = 无人物出镜（纯景物）

---

## 四、Agent 2 — Visual Director（视觉执导）

### 职责

接收 Screenwriter 的叙事分镜 → 为每个分镜生成 AI 可执行的 image/video prompt + 摄像机指令 + 模型推荐。

### 输入

Task 1（Screenwriter）的完整输出通过 CrewAI `context=[task_screenwrite]` 传递。

### 输出（纯 JSON 数组）

```json
[
  {
    "segment_id": 1,
    "image_prompt": "...",
    "video_prompt": "...",
    "camera_direction": {
      "subject": "...",
      "action": "...",
      "camera_movement": "...",
      "composition": "...",
      "lighting": "...",
      "ambiance": "..."
    },
    "model_recommendation": "veo" | "seedance" | "grok" | "wan2.2"
  }
]
```

### 实际输出（3 个分镜对比）

#### 分镜 1 — `story` 开场大远景

```json
{
  "segment_id": 1,
  "image_prompt": "Extreme long shot, desolate rocky landscape under vast swirling nebula sky, night, single point of light from old brass lantern flickering in distance, volumetric fog, 8k resolution, cinematic composition, wide angle lens, mysterious ambiance, photorealistic, indie film style.",
  "video_prompt": "Slow push in towards the distant lantern light, dust motes floating in nebular light, subtle camera drift, 15 seconds duration, transition hint: fade into close up of face.",
  "camera_direction": {
    "subject": "Distant landscape and lantern light",
    "action": "Camera slowly pushes forward",
    "camera_movement": "Slow Dolly In",
    "composition": "Extreme Long Shot (ELS), Center Framed",
    "lighting": "Natural Nebula Glow, Low Key",
    "ambiance": "Mysterious, Silent, Vast"
  },
  "model_recommendation": "veo"
}
```

#### 分镜 4 — `sing` 演唱特写（角色描述完整内联）

```json
{
  "segment_id": 4,
  "image_prompt": "Medium shot, The Wanderer Androgynous, 25-30, Weathered face, deep-set eyes reflecting starlight, short tousled hair, slight stubble, Worn leather jacket, dark grey trousers, heavy boots, carrying an old brass lantern, inside dimly lit cave, lantern illuminating face from side, raw expression, emotional intensity, cinematic lighting, volumetric dust, intimate framing, 8k.",
  "video_prompt": "Subject singing directly to camera, mouth moving with raw emotion, lantern light flickering slightly, subtle body sway, 30 seconds duration, transition hint: dissolve into montage.",
  "camera_direction": {
    "subject": "The Wanderer singing",
    "action": "Singing performance, emotional",
    "camera_movement": "Static Medium Shot",
    "composition": "Medium Shot, Eye Level",
    "lighting": "Lantern Key Light, High Contrast",
    "ambiance": "Intimate, Raw, Emotional"
  },
  "model_recommendation": "seedance"
}
```

#### 分镜 5 — `story` 蒙太奇（Grok 风格化）

```json
{
  "segment_id": 5,
  "image_prompt": "Montage sequence composition, The Wanderer's hands touching cold metal, map on rough wooden table, silhouette against sunrise, desaturated colors with warm amber accent, nostalgic mood, stylized art direction, film grain overlay, 8k.",
  "video_prompt": "Rhythmic cuts between hands on metal, map examination, and silhouette at sunrise, fast motion blur on cuts, color desaturation transition, 30 seconds duration, transition hint: cut to cliff edge.",
  "camera_direction": {
    "subject": "Various details (hands, map, silhouette)",
    "action": "Fast cuts, touching, observing",
    "camera_movement": "Dynamic Cuts",
    "composition": "Close Up / Medium Shot alternating",
    "lighting": "Desaturated, Natural Sunrise",
    "ambiance": "Nostalgic, Reflective, Desaturated"
  },
  "model_recommendation": "grok"
}
```

### 模型路由逻辑

| 镜头类型 | 推荐模型 | 原因 |
|---|---|---|
| 写实电影感场景 | `veo` | 高保真、景深、光线 |
| 演唱 / 舞蹈表演 | `seedance` | 人物动作流畅、口型 |
| 风格化 / 蒙太奇 | `grok` | 抽象、快剪、色彩风格 |
| 本地兜底 | `wan2.2` | 无网络/低成本 |

### Frame-chaining 设计

`video_prompt` 末尾的 `transition hint: fade into close up of face` 不是装饰——Phase 2 执行时，**上一个镜头的最后一帧**会被 FFmpeg 提取，作为**下一个镜头的 first_frame 参考图**传给视频模型，实现帧间一致性过渡。

---

## 五、Agent 3 — Music Producer（音乐设计）

### 职责

基于完整视觉方案（叙事 + 摄影），设计与分镜情绪节奏精确同步的音乐生成计划。

### 输入

Task 1 + Task 2 完整输出（`context=[task_screenwrite, task_direct]`）。

### 输出（只输出 music_plan，不重复 storyboard）

```json
{
  "music_plan": {
    "music_prompt": "Cinematic ambient post-rock track blending melancholic neo-classical elements with orchestral swells. Starts with sparse wind synthesis and deep, resonant cello notes in C# minor (60 BPM), building through textured guitar layers and choir harmonics into a triumphant climax at 90 BPM. Instrumentation: cello, acoustic guitar, synth pads, epic choir, orchestral percussion. No lyrics. Dynamic range from intimate solo to full orchestral wall-of-sound. Reference: Explosions in the Sky meets Hans Zimmer.",
    "model_recommendation": "acestep",
    "needs_vocal": false,
    "structure_map": [
      {"section": "Intro",   "start_time": 0.0,   "end_time": 15.0,  "description": "Sparse cello, match desolate landscape ELS"},
      {"section": "Verse 1", "start_time": 15.0,  "end_time": 60.0,  "description": "Builds with guitar layers, match wanderer walking shots"},
      {"section": "Chorus",  "start_time": 60.0,  "end_time": 90.0,  "description": "Full orchestra swell, match cave singing performance"},
      {"section": "Bridge",  "start_time": 90.0,  "end_time": 120.0, "description": "Stripped back, match memory montage"},
      {"section": "Outro",   "start_time": 150.0, "end_time": 180.0, "description": "Fade with solo cello, match final cliff walk-away"}
    ],
    "sync_points": [
      {"time": 0.0,   "event": "First lantern flicker — silence break"},
      {"time": 60.0,  "event": "Orchestral hit — cut to cave performance"},
      {"time": 90.0,  "event": "Percussion drop — montage begins"},
      {"time": 120.0, "event": "Climax peak — cliff edge singing"}
    ]
  }
}
```

### 音乐模型选择

| 模型 | 适用场景 |
|---|---|
| `acestep` | 器乐 / 无人声 / 风格精确控制 |
| `suno` | 需要歌词演唱 |
| `lyria` | Google 高保真器乐 |

---

## 六、PlanningService 合并（三路输出 → 一个 plan）

```
Agent 1 输出           Agent 2 输出          Agent 3 输出
character_bank    +    [shot objects]    +    music_plan
storyboard               ↑ 按 segment_id 回填进 storyboard
     │                        │                    │
     └────────────────────────▼────────────────────┘
                    _merge_planning_tasks()
                              │
                    plan = {
                      character_bank: {...},
                      storyboard: [
                        {segment_id, label, times, description,
                         mood, characters,
                         image_prompt,      ← Agent 2 回填
                         video_prompt,      ← Agent 2 回填
                         camera_direction,  ← Agent 2 回填
                         model_recommendation} ← Agent 2 回填
                      ],
                      music_plan: {...}
                    }
```

**合并策略**：只补充（`not in seg`），不覆盖已有字段，Agent 2 的 prompt 填入 Agent 1 的骨架里。若 `segment_id` 对不上，按数组位置兜底匹配。

---

## 七、Phase 1 — 并行生成图片 + 音乐

```
run_full_pipeline (Celery)
  │
  ├─ 为每个 storyboard 段落创建 image Task
  │    prompt = segment["image_prompt"]
  │    model  = model_prefs["image"] || "z-image"
  │
  ├─ 创建 music Task
  │    prompt = music_plan["music_prompt"]
  │    model  = music_plan["model_recommendation"] || "acestep"
  │
  └─ chord(all tasks)(run_video_phase)
       → 全部完成后自动触发 Phase 2，本 worker 立即释放
```

**chord 并行**：6 张图片 + 1 首音乐同时生成，互不阻塞。

---

## 八、Phase 2 — 顺序视频生成（帧链接）

```
run_video_phase
  │
  ├─ ShotRouter.plan_all_shots(storyboard, visual_style)
  │    ↓ 对每个分镜
  │    ├─ label == "sing" → model = seedance (或按风格: 国风→veo)
  │    └─ label == "story" → model = veo (赛博朋克→grok, 蒙太奇→grok)
  │
  └─ 顺序执行（保证帧链接）
       shot 1: first_frame = image_media[0].url
               → 生成视频 → 提取最后一帧
       shot 2: first_frame = shot1_last_frame
               → 生成视频 → 提取最后一帧
       shot 3: first_frame = shot2_last_frame
               → ...
       shot N: first_frame = shot(N-1)_last_frame
```

**帧提取实现**（FFmpeg）：
```bash
ffmpeg -sseof -0.1 -i shot_N.mp4 -update 1 -q:v 2 last_frame.jpg
```
提取最后 0.1 秒内的最后一帧，作为下一镜头的视觉起点。

---

## 九、Phase 3 — 合成最终 MV

```
run_compose_phase
  │
  ├─ 查询 music Task（Phase 1 已完成）→ 取 audio_url
  │
  ├─ FFmpeg concat 所有 video 片段
  │    ffmpeg -f concat -safe 0 -i list.txt -c copy concat.mp4
  │
  ├─ FFmpeg merge 音频
  │    ffmpeg -i concat.mp4 -i music.mp3
  │          -map 0:v -map 1:a
  │          -af loudnorm=I=-14:LRA=11:TP=-1.5  ← -14 LUFS 标准化
  │          final.mp4
  │
  └─ 上传 MinIO → 更新 project.status = "done"
       WebSocket 推送 "completed" 给前端
```

---

## 十、端到端数据流汇总

```
用户输入: "孤独旅人星空徒步MV，史诗感，大气磅礴"
          │
          ├─ music_analysis (可选): BPM=87.5, sections=[intro/verse/chorus/bridge/outro]
          │
          ├─ Agent 1 Screenwriter:
          │    character_bank → The_Wanderer {外貌+服装完整档案}
          │    storyboard → 6段分镜 [story×5, sing×1@60-90s]
          │
          ├─ Agent 2 Director:
          │    seg1: image_prompt="荒野星云...8k" · video_prompt="Slow dolly in..." · model=veo
          │    seg4: image_prompt="旅人特写+完整外貌描述...8k" · video_prompt="singing..." · model=seedance
          │    seg5: image_prompt="蒙太奇构图..." · video_prompt="fast cuts..." · model=grok
          │
          ├─ Agent 3 Music Producer:
          │    music_prompt="C# minor, 60→90BPM, cello+choir+orchestra, Hans Zimmer style"
          │    model=acestep  needs_vocal=false
          │    sync_points=[0s:silence, 60s:orchestral hit, 90s:percussion drop]
          │
          ├─ Phase 1 (并行):
          │    6× Z-Image  → 6张参考图
          │    1× ACEStep  → 180s 配乐
          │
          ├─ Phase 2 (顺序):
          │    shot1 → Veo    (story · first_frame=image1)    → 15s 视频
          │    shot2 → Veo    (story · first_frame=shot1末帧) → 30s 视频
          │    shot3 → Veo    (story · first_frame=shot2末帧) → 15s 视频
          │    shot4 → Seedance (sing · first_frame=shot3末帧) → 30s 视频
          │    shot5 → Grok  (story · first_frame=shot4末帧) → 30s 视频
          │    shot6 → Veo    (story · first_frame=shot5末帧) → 30s 视频
          │
          └─ Phase 3 Compose:
               concat(shot1-6) + merge(music) + -14LUFS
               → final_mv.mp4  ✓
```

---

## 十一、关键设计决策速查

| 问题 | 解决方案 | 位置 |
|---|---|---|
| 单任务输出 27K+ 字符导致截断 | 拆成 3 个独立任务，每个 3–8K | `crew.py` |
| `max_tokens=2000` 不够 | 调整为 8192 | `_qwen_llm()` |
| Director 返回 list，其他返回 dict | `_extract_json()` 统一处理 dict\|list\|None | `planning_service.py:83` |
| segment_id int vs string 不匹配 | 先 ID 查找，失败按位置兜底 | `planning_service.py:160` |
| 角色视觉不一致 | character_bank 内联进每个 image_prompt | `agent 2 prompt design` |
| 视频帧间割裂感 | 帧链接：上一帧 = 下一帧起始图 | `shot_router.py:extract_last_frame` |
| 并行 vs 串行 | Phase1 chord 并行，Phase2 顺序（帧依赖） | `generation_tasks.py` |
| 音量不统一 | FFmpeg loudnorm -14 LUFS | `compose_service.py` |
| 质量兜底 | Review Crew（已实现，human-in-loop 预留） | `crew.py:build_review_crew` |
