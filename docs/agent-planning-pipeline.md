# 分镜 Agent 链路设计文档

## 概览

Planning Crew 是 AIMV Studio 的创作核心，由三个串行 Agent 组成，将用户的一句话创作意图转化为完整的"可执行生产计划"（storyboard + character bank + music plan）。

```
用户意图 + 音乐分析
        │
        ▼
┌───────────────────┐
│  Agent 1          │  任务：剧本创作
│  MV Screenwriter  │  → character_bank + storyboard（叙事层）
└────────┬──────────┘
         │ context 传递
         ▼
┌───────────────────┐
│  Agent 2          │  任务：视觉执导
│  MV Visual        │  → 每个分镜的 image/video prompt（执行层）
│  Director         │
└────────┬──────────┘
         │ context 传递
         ▼
┌───────────────────┐
│  Agent 3          │  任务：音乐设计
│  Music Producer   │  → music_plan（音乐层）
└───────────────────┘
         │
         ▼
   PlanningService._merge_planning_tasks()
   （三路输出合并为一个 plan dict）
```

框架：CrewAI · 模型：Qwen3.5-9B（OpenAI compat API）· 运行模式：sequential

---

## Agent 详细设计

### Agent 1 — MV Screenwriter（剧本创作）

**职责**：读懂用户意图，建立角色库，划分叙事分镜。

| 属性 | 值 |
|---|---|
| role | `MV Screenwriter` |
| temperature | 0.7 |
| max_tokens | 8192 |
| context 来源 | 用户意图 + 音乐分析（BPM / duration / sections） |

**输入**（task description 注入）：
```
## User Creative Intent
帮我做一个关于孤独旅人在星空下徒步的MV，风格史诗感，配乐大气磅礴

## Music Analysis
BPM: unknown  Duration: unknowns
Sections: []  Lyrics: []  Energy curve: []

## Style Preferences
Visual style: 独立电影  Music style: auto  Mood: epic
```

**输出格式**：
```json
{
  "character_bank": {
    "<key>": {
      "name": "...",
      "age_range": "...",
      "gender": "...",
      "appearance": "...",
      "outfit": "...",
      "style_tags": [...],
      "role": "...",
      "personality": "..."
    }
  },
  "storyboard": [
    {
      "segment_id": 1,
      "label": "story" | "sing",
      "start_time": 0.0,
      "end_time": 15.0,
      "description": "...",
      "mood": "...",
      "characters": [...]
    }
  ]
}
```

**实际输出示例**（孤独旅人MV）：

```json
{
  "character_bank": {
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
  },
  "storyboard": [
    {
      "segment_id": 1,
      "label": "story",
      "start_time": 0.0,
      "end_time": 15.0,
      "description": "Extreme long shot of a desolate, rocky landscape under a vast, swirling nebula sky. Silence. A single point of light (the lantern) flickers in the distance.",
      "mood": "Mysterious",
      "characters": []
    },
    {
      "segment_id": 2,
      "label": "story",
      "start_time": 15.0,
      "end_time": 45.0,
      "description": "Close up on The Wanderer's face. They look up at the stars, breathing heavily. Handheld camera shake emphasizes isolation. Grainy film texture applied.",
      "mood": "Melancholic",
      "characters": ["The_Wanderer"]
    },
    {
      "segment_id": 4,
      "label": "sing",
      "start_time": 60.0,
      "end_time": 90.0,
      "description": "The Wanderer sings directly to the camera in a dimly lit cave. The lantern illuminates their face. Emotional, raw vocal performance.",
      "mood": "Intimate",
      "characters": ["The_Wanderer"]
    }
  ]
}
```

**设计要点**：
- `label: "sing"` 表示演唱镜头（歌手面向镜头），`"story"` 表示叙事场景
- `start_time / end_time` 与音乐 sections 对齐（有音乐分析时）
- 角色库一次性定义全片角色，后续 Agent 直接引用，保证视觉一致性

---

### Agent 2 — MV Visual Director（视觉执导）

**职责**：接收 Screenwriter 的叙事分镜，为每个镜头生成 AI 可执行的 image/video prompt 和摄像机指令。

| 属性 | 值 |
|---|---|
| role | `MV Visual Director` |
| temperature | 0.7 |
| max_tokens | 8192 |
| context 来源 | Task 1 的完整输出（character_bank + storyboard） |

**输出格式**（纯 JSON 数组，不包裹 dict）：
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

**实际输出示例（3 个镜头对比）**：

#### 镜头 1 — `story` 类，开场大远景
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

#### 镜头 4 — `sing` 类，演唱特写
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

#### 镜头 5 — `story` 类，蒙太奇剪辑
```json
{
  "segment_id": 5,
  "image_prompt": "Montage sequence composition, The Wanderer ... hands touching cold metal, map on table, silhouette against sunrise, desaturated colors, nostalgic mood, stylized art style, 8k.",
  "video_prompt": "Rhythmic cuts between hands on metal, map examination, and silhouette, fast motion blur, color desaturation transition, 30 seconds duration, transition hint: cut to cliff edge performance.",
  "camera_direction": {
    "subject": "Various details (hands, map, silhouette)",
    "action": "Fast cuts, touching, observing",
    "camera_movement": "Dynamic Cuts",
    "composition": "Close Up / Medium Shot",
    "lighting": "Desaturated, Natural",
    "ambiance": "Nostalgic, Reflective, Desaturated"
  },
  "model_recommendation": "grok"
}
```

**设计要点**：
- `image_prompt` 把 character_bank 中的外貌描述直接内联进 prompt（不依赖模型的"记忆"）
- `model_recommendation` 依据镜头类型选模型：
  - `veo` — 写实电影感镜头
  - `seedance` — 演唱类（角色面对镜头 + 口型同步需求）
  - `grok` — 风格化 / 蒙太奇 / 抽象类
  - `wan2.2` — 本地部署兜底
- `transition hint` 写在 video_prompt 末尾，为 frame-chaining（上一帧 = 下一帧起始帧）提供提示

---

### Agent 3 — Music Producer（音乐设计）

**职责**：基于完整视觉方案，设计与分镜情绪节奏精确同步的音乐生成计划。

| 属性 | 值 |
|---|---|
| role | `Music Producer` |
| temperature | 0.7 |
| max_tokens | 8192 |
| context 来源 | Task 1 + Task 2 的完整输出（叙事 + 视觉执导） |

**输出格式**（只输出 music_plan，不重复 storyboard）：
```json
{
  "music_plan": {
    "music_prompt": "...",
    "model_recommendation": "acestep" | "suno" | "lyria",
    "needs_vocal": true | false,
    "structure_map": [
      {
        "section": "Intro",
        "start_time": 0.0,
        "end_time": 30.0,
        "description": "..."
      }
    ],
    "sync_points": [
      { "time": 0.0, "event": "..." }
    ]
  }
}
```

**实际输出示例**：
```json
{
  "music_plan": {
    "music_prompt": "Cinematic ambient post-rock track blending melancholic neo-classical elements with orchestral swells. Starts with sparse wind synthesis and deep, resonant cello notes in C# minor (60 BPM), building through textured guitar layers and choir harmonics into a triumphant climax at 90 BPM. Instrumentation: cello, acoustic guitar, synth pads, epic choir, orchestral percussion. No lyrics. Dynamic range from intimate solo to full orchestral wall-of-sound. Reference: Explosions in the Sky meets Hans Zimmer.",
    "model_recommendation": "acestep",
    "needs_vocal": false,
    "structure_map": [
      { "section": "Intro",   "start_time": 0.0,  "end_time": 15.0,  "description": "Sparse cello, match desolate landscape ELS" },
      { "section": "Verse 1", "start_time": 15.0, "end_time": 60.0,  "description": "Builds with guitar, match wanderer walking shots" },
      { "section": "Chorus",  "start_time": 60.0, "end_time": 90.0,  "description": "Full orchestra swell, match cave singing performance" },
      { "section": "Bridge",  "start_time": 90.0, "end_time": 120.0, "description": "Stripped back, match memory montage" },
      { "section": "Outro",   "start_time": 150.0,"end_time": 180.0, "description": "Fade with solo cello, match final cliff walk-away" }
    ],
    "sync_points": [
      { "time": 0.0,   "event": "First lantern flicker — silence break" },
      { "time": 60.0,  "event": "Orchestral hit — cut to cave performance" },
      { "time": 90.0,  "event": "Percussion drop — montage begins" },
      { "time": 120.0, "event": "Climax peak — cliff edge singing" }
    ]
  }
}
```

**设计要点**：
- 只输出 `music_plan`，不重复 storyboard（避免 LLM 因输出过长而截断）
- `structure_map` 中的时间区间与 storyboard 的 `start_time / end_time` 对齐
- `sync_points` 用于后期 Celery 任务的音视频对齐裁剪
- 模型选择：`acestep`（器乐）/ `suno`（需要歌词演唱）/ `lyria`（高保真）

---

## PlanningService 合并逻辑

三个 Agent 各自输出不同的 JSON 结构，由 `PlanningService._merge_planning_tasks()` 合并：

```python
# 代码位置：backend/app/services/planning_service.py

def _merge_planning_tasks(self, result) -> dict:
    # Task 0: Screenwriter → character_bank + storyboard（叙事骨架）
    sw = self._extract_json(_raw(0)) or {}
    character_bank = sw.get("character_bank", {})
    storyboard = sw.get("storyboard", [])

    # Task 1: Director → shot 数组（按 segment_id 匹配，回填进 storyboard）
    dir_val = self._extract_json(_raw(1))
    if isinstance(dir_val, list):
        director_shots = dir_val
    # ... 按 segment_id 匹配 or 按位置兜底
    for i, seg in enumerate(storyboard):
        shot = by_id.get(seg["segment_id"]) or director_shots[i]
        for key in ("image_prompt", "video_prompt", "camera_direction", "model_recommendation"):
            if key in shot and key not in seg:
                seg[key] = shot[key]  # 只补充，不覆盖

    # Task 2: Music Producer → music_plan
    mp = self._extract_json(_raw(2)) or {}
    music_plan = mp.get("music_plan", {})

    return {"character_bank": ..., "storyboard": ..., "music_plan": ...}
```

合并后的最终 plan 结构：

```
plan
├── character_bank          ← Agent 1
│   └── The_Wanderer: {...}
├── storyboard              ← Agent 1 骨架 + Agent 2 prompt 回填
│   ├── [0]: segment_id, label, times, description, mood, characters
│   │        + image_prompt, video_prompt, camera_direction, model_recommendation
│   └── ...
├── music_plan              ← Agent 3
│   ├── music_prompt
│   ├── model_recommendation
│   ├── structure_map
│   └── sync_points
└── music_analysis          ← 原始音乐分析透传（如有上传音频）
```

---

## 关键设计决策

| 问题 | 解决方案 |
|---|---|
| LLM 输出截断（原来单任务要输出 27K 字符）| 拆分为三个独立任务，每个任务输出量控制在 3K–8K |
| `max_tokens=2000` 不够 | 调整为 8192（约 32K 字符输出上限）|
| Director 输出 list，其他输出 dict | `_extract_json()` 统一处理 `dict \| list \| None` |
| segment_id 不匹配（int vs string）| 先 ID 查找，失败则按数组位置兜底合并 |
| 解析逻辑"补丁叠补丁" | 统一为 `_extract_json`：整串 JSON → 代码块 → 扫描第一个 `[{` |

---

## 扩展说明：Review Crew（质检 Agent）

除 Planning Crew 外，还有一个独立的 `build_review_crew`，在生成资产后运行：

```
生成的图片/视频资产
        │
        ▼
┌─────────────────┐
│  Quality        │  对比原始 storyboard + character_bank
│  Director       │  → 评分 + 标记需要重生成的资产
└─────────────────┘
```

输出：
```json
{
  "overall_score": 3.8,
  "passed": true,
  "asset_reviews": [
    {
      "asset_id": "shot_001",
      "visual_quality": 4,
      "character_consistency": 3,
      "prompt_adherence": 4,
      "physical_plausibility": 4
    }
  ],
  "regenerate_ids": []
}
```

> 当前 Review Crew 已实现但未接入主流程，预留作为 human-in-the-loop 审核节点。
