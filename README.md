<div align="center">

# AIMV Studio

**基于 Agent 与大模型的 MV 内容生成系统**

*An end-to-end music video generation system driven by multi-agent AI orchestration*

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?logo=python&logoColor=white)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.110+-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com)
[![Vue](https://img.shields.io/badge/Vue-3.x-4FC08D?logo=vue.js&logoColor=white)](https://vuejs.org)
[![CrewAI](https://img.shields.io/badge/CrewAI-Multi--Agent-8d5cff)](https://crewai.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

</div>

---

四个专职 CrewAI Agent（编剧 / 导演 / 音乐制作人 / 验证）协作，将一句创意描述转化为完整的 MV：
分镜规划 → 图像生成 → 视频合成 → 音乐制作 → 音视频对齐 → 多平台导出。

Four specialized CrewAI agents collaborate to turn a text description into a complete music video:
storyboard planning → image generation → video synthesis → music production → A/V alignment → export.

---

## 界面预览 / Screenshots

### 首页 Hero / Landing Hero
![Home Hero](docs/screenshots/home_hero.png)

### Agent 协作流水线 / Agent Pipeline
![Agent Pipeline](docs/screenshots/pipeline.png)

### 音乐分析引擎 / Music Analysis Engine
![Music Analysis](docs/screenshots/music_demo.png)

### AI 模型矩阵 / Model Matrix
![Model Matrix](docs/screenshots/models.png)

### 多平台导出 / Multi-Platform Export
![Export Presets](docs/screenshots/export.png)

<table>
  <tr>
    <td align="center"><b>完整首页 / Full Landing</b></td>
    <td align="center"><b>公开画廊 / Gallery</b></td>
    <td align="center"><b>登录 / Sign In</b></td>
    <td align="center"><b>创作台 / Create</b></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/home.png" alt="Home"/></td>
    <td><img src="docs/screenshots/gallery.png" alt="Gallery"/></td>
    <td><img src="docs/screenshots/login.png" alt="Login"/></td>
    <td><img src="docs/screenshots/create.png" alt="Create"/></td>
  </tr>
</table>

---

## 系统架构 / Architecture

```
用户输入 / User Input
  文字描述 + 上传音频 / Text description + uploaded audio
        │
        ▼
┌─────────────────────────────────────────────────────────┐
│               规划阶段 Planning Phase (CrewAI)           │
│                                                         │
│   编剧 Screenwriter ──► 导演 Director ──► 音乐制作人     │
│         │                    │           Music Producer │
│   故事大纲 + 分镜        镜头提示词           音乐方案    │
│   CharacterBank         模型路由决策         模型路由决策 │
└─────────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────────┐
│                 生成阶段 Generation Phase (Celery 异步队列)         │
│                                                                   │
│  MusicAnalyzer           AI 生图 Image          AI 生视频 Video    │
│  ├ librosa BPM/节拍  ──► Z-image (开源/local)  ──► Wan2.2 14B     │
│  ├ htdemucs 音轨分离     CharacterBank              Seedance 2.0   │
│  ├ whisper 歌词转录      角色外观锚点               Veo 3.1        │
│  └ 段落结构分割                                    Grok Video 1.0  │
│       │                                      ShotRouter           │
│  BPM → 分镜时长约束                           sing / story 双轨    │
│  歌词 → SRT 字幕                              Frame Chaining       │
│  段落 → Agent 上下文         AI 生音乐 Music        │              │
│       └──────────────► ACEStep 1.5 (本地) ◄───────┘              │
│                         Suno (含人声)                              │
│                         Google Lyria (高保真)                      │
│                         Loudnorm −14 LUFS                         │
└───────────────────────────────────────────────────────────────────┘
        │
        ▼
┌──────────────────────────────────────┐
│  验证 Verifier Agent  (自动重试 ×3)   │
│  画面质量 / 角色一致性 / 提示词契合度  │
│  评分 1–5，低于 3 分触发重试          │
└──────────────────────────────────────┘
        │
        ▼
  FFmpeg 合成 → 字幕烧录 → 多平台导出
  抖音(9:16) / B站(16:9) / YouTube(HQ) / 小红书(3:4)
```

---

## 核心功能 / Features

### 🤖 多 Agent 协作规划 / Multi-Agent Planning

| Agent | 职责 / Role | 输出 / Output |
|---|---|---|
| 编剧 Screenwriter | 解析用户意图，结合音乐分析生成故事大纲 | JSON 分镜脚本 + CharacterBank |
| 导演 Director | 为每个镜头生成图像/视频提示词，决定模型路由 | Shot prompts + 模型路由表 |
| 音乐制作人 Music Producer | 设计音乐方案，决定开源/闭源模型选择 | 音乐提示词 + 模型路由 |
| 验证 Verifier | 多维度质量评分，不达标自动触发重试 | 质量报告 + 重试指令 |

LLM 引擎：**GPT-4o** / **Gemini 2.5 Flash**（SSE 流式输出）

---

### 🎵 音乐分析 / Music Analysis

上传音频后，生成前先完成结构分析，驱动分镜时长规划：

- **BPM + 节拍检测** — librosa，节拍时间戳传递给视频剪辑点
- **音轨分离** — htdemucs，人声 / 鼓 / 贝斯 / 其他四轨
- **歌词转录** — faster-whisper，带时间轴，自动生成 SRT 字幕
- **段落结构分割** — MFCC + chroma 特征 → 递归相似矩阵 → agglomerative 聚类 → 按 RMS 能量分配 intro / verse / chorus / bridge / outro 标签

---

### 🎬 视频生成双轨策略 / Dual-Track Video

ShotRouter 根据分镜类型（演唱镜头 sing / 叙事镜头 story）和视觉风格自动路由：

| 模型 | 类型 | 适用场景 |
|---|---|---|
| **Wan2.2 14B** | 开源，本地部署 | 调试 / 数据隐私 / LoRA 微调 |
| **Seedance 2.0** | 闭源 API | 舞蹈 / 动作 / 高流畅度 |
| **Veo 3.1** | 闭源 API | 电影级画质 / 长镜头叙事 |
| **Grok Video 1.0** | 闭源 API | 风格化 / 快速生成 |

**Frame Chaining**：上一镜头末帧作为下一镜头参考图，保持视觉连贯性。

---

### 🎶 音乐生成双轨策略 / Dual-Track Music

| 模型 | 类型 | 适用场景 |
|---|---|---|
| **ACEStep 1.5** | 开源，本地部署 | 4GB 显存可跑，支持 LoRA 微调 |
| **Suno** | 闭源 API | 含人声 + 歌词的完整歌曲 |
| **Google Lyria** | 闭源 API | 高保真纯器乐 / 复杂编曲 |

生成后统一进行 **Loudness 标准化（−14 LUFS / −1.5 dBTP）**，符合 Spotify / YouTube / Apple Music 规范。

---

### 🖼️ 人物一致性 / Character Consistency

- **CharacterBank**：存储角色外貌、服装、风格标签，自动附加到每个镜头的提示词
- **Z-image（开源）**：生成主角形象，首张图作为后续镜头的外观锚点
- 支持 7 种视觉风格：韩娱练习生 / 国风古典 / 赛博朋克 / 复古迪斯科 / 独立电影感 / 都市甜酷 / 幻想童话

---

### 📊 其他功能 / Other

- **A/B 版本对比** — 同一段落并发调用多个模型，用户择优选择
- **质量自动把关** — VerifierAgent 评分低于 3 分触发重试，最多 3 次
- **字幕自动烧录** — 基于 whisper 转录结果生成 SRT，导出时一键烧录
- **多平台导出** — 抖音 9:16 / B站 16:9 / YouTube HQ / 小红书 3:4，自动重编码
- **WebSocket 实时进度** — 前端全程追踪生成状态
- **画廊与点赞** — 公开发布的 MV 支持展示与互动

---

## 模型支持 / Model Support

| 模态 Modality | 开源 Open-source | 闭源 Closed-source |
|---|---|---|
| 图像 Image | Z-image（本地） | — |
| 视频 Video | Wan2.2 14B（Apache 2.0） | Seedance 2.0 · Veo 3.1 · Grok Video 1.0 |
| 音乐 Music | ACEStep 1.5（LoRA 支持） | Suno · Google Lyria |
| LLM | — | GPT-4o · Gemini 2.5 Flash |

---

## 技术栈 / Tech Stack

| 层次 | 技术 |
|---|---|
| 前端 Frontend | Vue 3 + TypeScript + Vite + Element Plus |
| 后端 Backend | Python FastAPI + SQLAlchemy (async) + Pydantic |
| Agent 框架 | CrewAI |
| 异步队列 Queue | Celery + RabbitMQ |
| 数据库 Database | PostgreSQL |
| 缓存 / 消息 Cache | Redis |
| 对象存储 Storage | MinIO（开发）|
| 容器化 Container | Docker + Docker Compose |
| 媒体处理 Media | FFmpeg |

---

## 快速开始 / Quick Start

### 前置依赖 / Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 20+
- FFmpeg

### 1. 启动基础服务 / Start Infrastructure

```bash
docker compose up -d postgres redis rabbitmq minio
```

### 2. 后端 / Backend

```bash
cd backend
cp .env.example .env        # 填写 API Keys / fill in your API keys
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Celery Worker

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

### 4. 前端 / Frontend

```bash
cd frontend
npm install
npm run dev                  # http://localhost:5173
```

> 后端 Swagger 文档 / Backend API docs: `http://localhost:8000/docs`

---

## 环境变量 / Environment Variables

复制 `backend/.env.example` 并填写以下配置 / Copy `backend/.env.example` and fill in:

```env
# 数据库 / Database
DATABASE_URL=postgresql+asyncpg://aimv:aimv@localhost:5432/aimv

# 缓存 + 队列 / Cache + Queue
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//

# JWT
SECRET_KEY=change-me-in-production

# LLM（二选一或都填 / at least one required）
OPENAI_API_KEY=
GEMINI_API_KEY=

# 图像生成 / Image — Z-image 本地服务地址
Z_IMAGE_BASE_URL=http://localhost:7860
Z_IMAGE_API_KEY=

# 视频生成 / Video（闭源，按需填写 / optional, fill as needed）
SEEDANCE_API_KEY=
VEO_API_KEY=
GROK_VIDEO_API_KEY=

# 音乐生成 / Music（闭源，按需填写）
SUNO_API_KEY=
LYRIA_API_KEY=

# 本地模型路径 / Local model paths
ACESTEP_MODEL_PATH=     # e.g. /models/acestep-1.5
WAN_MODEL_PATH=         # e.g. /models/wan2.2-14b

# MinIO（开发默认值 / dev defaults）
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

---

## API 接口 / API Reference

| 方法 | 路径 | 说明 |
|---|---|---|
| `POST` | `/api/v1/auth/register` | 注册 / Register |
| `POST` | `/api/v1/auth/login` | 登录，返回 JWT / Login |
| `GET` | `/api/v1/auth/me` | 当前用户 / Current user |
| `POST` | `/api/v1/projects` | 创建项目 / Create project |
| `GET` | `/api/v1/projects` | 项目列表 / List projects |
| `POST` | `/api/v1/projects/{id}/chat` | 与 AI 导演对话（SSE 流式）/ Chat |
| `POST` | `/api/v1/projects/{id}/generate/image` | 生成图像 / Generate image |
| `POST` | `/api/v1/projects/{id}/generate/video` | 生成视频片段 / Generate video |
| `POST` | `/api/v1/projects/{id}/generate/music` | 生成音乐 / Generate music |
| `POST` | `/api/v1/projects/{id}/pipeline/start` | 一键跑完整流水线 / Full pipeline |
| `POST` | `/api/v1/projects/{id}/compare` | A/B 模型对比 / Compare models |
| `POST` | `/api/v1/projects/{id}/export` | 导出指定平台格式 / Export |
| `GET` | `/api/v1/gallery` | 公开画廊 / Public gallery |
| `WS` | `/ws/projects/{id}/progress` | 实时生成进度 / Live progress |

---

## 项目结构 / Project Structure

```
aimv-studio/
├── backend/
│   ├── app/
│   │   ├── api/v1/                  # REST 接口层
│   │   │   ├── auth.py              # 认证 / JWT
│   │   │   ├── project.py           # 项目 CRUD
│   │   │   ├── chat.py              # SSE 对话流
│   │   │   ├── generate.py          # 单模态生成触发
│   │   │   ├── pipeline.py          # 全流水线触发
│   │   │   ├── compare.py           # A/B 对比
│   │   │   ├── export.py            # 平台导出
│   │   │   └── gallery.py           # 公开画廊
│   │   ├── core/
│   │   │   ├── agents/
│   │   │   │   ├── crew.py          # CrewAI 四 Agent 定义 + Task 链
│   │   │   │   └── prompts.py       # Agent 系统提示词
│   │   │   ├── music_analyzer.py    # librosa / htdemucs / faster-whisper / SRT
│   │   │   ├── character_bank.py    # 跨镜头角色一致性
│   │   │   ├── shot_router.py       # Sing/Story 路由 + Frame Chaining
│   │   │   ├── verifier.py          # LLM 质量评分 + 重试
│   │   │   ├── llm_client.py        # OpenAI / Gemini SSE 流式客户端
│   │   │   └── model_router.py      # 视频/音乐模型智能路由
│   │   ├── adapters/                # 每个模型一个 Adapter
│   │   │   ├── base.py              # BaseModelAdapter 基类
│   │   │   ├── z_image.py           # Z-image（开源图像）
│   │   │   ├── wan_video.py         # Wan2.2 14B（开源视频）
│   │   │   ├── seedance.py          # Seedance 2.0
│   │   │   ├── veo.py               # Google Veo 3.1
│   │   │   ├── grok_video.py        # Grok Video 1.0
│   │   │   ├── acestep.py           # ACEStep 1.5（开源音乐）
│   │   │   ├── suno.py              # Suno
│   │   │   └── lyria.py             # Google Lyria
│   │   ├── services/
│   │   │   ├── planning_service.py  # MusicAnalyzer → CrewAI → 解析规划结果
│   │   │   ├── generation_service.py# Adapter 调度 + verify-retry 循环
│   │   │   └── compose_service.py   # FFmpeg 合成 / loudnorm / 字幕 / 导出
│   │   ├── workers/
│   │   │   ├── generation_tasks.py  # Celery: image / video / music / compose
│   │   │   └── export_tasks.py      # Celery: 平台重编码 + 字幕烧录
│   │   └── models/                  # SQLAlchemy ORM 数据模型
│   ├── alembic/                     # 数据库迁移
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── views/
│       │   ├── Home/                # 首页 Landing
│       │   ├── Create/              # 创作工作台
│       │   ├── Project/             # 项目管理
│       │   ├── Gallery/             # 公开画廊
│       │   ├── Editor/              # 后期编辑 + 导出
│       │   └── User/Login.vue       # 登录 / 注册
│       ├── components/
│       │   ├── ComparePanel.vue     # A/B 对比面板
│       │   └── SkeletonCard.vue     # 加载骨架屏
│       ├── stores/                  # Pinia 状态管理
│       ├── api/                     # Axios 封装
│       └── router/                  # Vue Router
├── docs/screenshots/                # UI 截图
├── docker-compose.yml
└── README.md
```

---

## 开发背景 / Background

本项目为本科毕业设计，课题名称：**基于 Agent 与大模型的 MV 内容生成系统设计与实现**。

核心研究问题：如何用 Agent 架构将 LLM 的意图理解能力与多个异构 AI 生成模型（图像 / 视频 / 音乐）整合为一条自动化的 MV 创作流水线，并通过音乐结构分析实现音视频的段落级对齐。

参考工作：[AutoMV](https://arxiv.org/abs/2512.12196)（首个开源多 Agent MV 生成系统）、[Wan2.2](https://arxiv.org/abs/2503.20314)、[ACE-Step 1.5](https://arxiv.org/abs/2602.00744) 等。

---

## License

MIT
