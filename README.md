# AIMV Studio

**基于 Agent 与大模型的 MV 内容生成系统** — An end-to-end music video generation system powered by multi-agent AI orchestration.

Four specialized CrewAI agents (Screenwriter / Director / Music Producer / Verifier) collaborate to turn a text description into a complete music video: storyboard planning → image generation → video synthesis → music production → audio-visual alignment → export.

---

## Architecture

```
User Input (text / uploaded audio)
        │
        ▼
┌─────────────────────────────────────────────────────┐
│              Planning Phase (CrewAI)                │
│  Screenwriter ──► Director ──► Music Producer       │
│       │               │              │              │
│  Storyboard      Shot prompts    Music prompt       │
│  CharacterBank   Model routing   Model routing      │
└─────────────────────────────────────────────────────┘
        │
        ▼
┌───────────────────────────────────────────────────────────────┐
│                   Generation Phase (Celery)                   │
│                                                               │
│  MusicAnalyzer   ──►  AI Image     ──►  AI Video             │
│  (librosa/demucs      (Z-image)         (Wan2.2 / Seedance /  │
│   /whisper)           CharacterBank     Veo 3.1 / Grok Video) │
│       │                                      │                │
│  BPM + beats                         ShotRouter               │
│  Lyrics → SRT                        Frame Chaining           │
│  Sections                                    │                │
│       │               AI Music               │                │
│       └──────────►  (ACEStep 1.5 /  ◄────────┘                │
│                      Suno / Lyria)                            │
│                    Loudness -14 LUFS                          │
└───────────────────────────────────────────────────────────────┘
        │
        ▼
┌─────────────────────────────────┐
│   Verifier Agent  (auto-retry)  │
│   Score: visual / consistency   │
│           / prompt adherence    │
└─────────────────────────────────┘
        │
        ▼
  FFmpeg Compose → Subtitle burn → Platform export
  (Douyin / Bilibili / YouTube / Xiaohongshu)
```

---

## Features

- **Multi-agent planning** — CrewAI orchestrates 4 agents with distinct roles; LLM (GPT-4o / Gemini 2.5 Flash) handles intent understanding and prompt generation
- **Music analysis** — librosa BPM/beat detection, htdemucs stem separation, faster-whisper lyrics transcription with real audio-structure segmentation (MFCC + chroma recurrence matrix)
- **Dual-track model strategy** — open-source local models for privacy/customization, closed-source APIs for quality; automatic routing by scene type
- **Character consistency** — CharacterBank stores visual anchors; Frame Chaining passes the last frame of each shot as reference for the next
- **Quality gate** — VerifierAgent scores every generated asset (1–5); anything below 3 triggers auto-retry (max 3 attempts)
- **Loudness normalization** — FFmpeg `loudnorm` to –14 LUFS / –1.5 dBTP after music generation
- **A/B comparison** — submit the same prompt to multiple models simultaneously, pick the winner
- **Platform export** — re-encode to per-platform specs with optional subtitle burn and watermark

---

## Model Support

| Modality | Open-source | Closed-source |
|---|---|---|
| Image | Z-image (local) | — |
| Video | Wan2.2 14B (local, Apache 2.0) | Seedance 2.0 · Veo 3.1 · Grok Video 1.0 |
| Music | ACEStep 1.5 (local, LoRA) | Suno · Google Lyria |
| LLM | — | GPT-4o · Gemini 2.5 Flash |

---

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | Vue 3 + TypeScript + Vite + Element Plus |
| Backend | Python FastAPI + SQLAlchemy (async) + Pydantic |
| Agent | CrewAI 4-agent pipeline |
| Queue | Celery + RabbitMQ |
| Database | PostgreSQL |
| Cache / Pub-Sub | Redis |
| Storage | MinIO (dev) |
| Container | Docker + Docker Compose |
| Post-processing | FFmpeg |

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- Python 3.11+
- Node.js 20+
- FFmpeg

### 1. Start infrastructure

```bash
docker compose up -d postgres redis rabbitmq minio
```

### 2. Backend

```bash
cd backend
cp .env.example .env   # fill in your API keys
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

### 3. Celery worker

```bash
cd backend
celery -A app.workers.celery_app worker --loglevel=info
```

### 4. Frontend

```bash
cd frontend
npm install
npm run dev            # http://localhost:5173
```

---

## Environment Variables

Copy `backend/.env.example` and fill in the following:

```env
# Database
DATABASE_URL=postgresql+asyncpg://aimv:aimv@localhost:5432/aimv

# Redis / Celery
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=amqp://guest:guest@localhost:5672//

# JWT
SECRET_KEY=change-me-in-production

# LLM
OPENAI_API_KEY=
GEMINI_API_KEY=

# Image
Z_IMAGE_BASE_URL=http://localhost:7860   # local Z-image API endpoint
Z_IMAGE_API_KEY=

# Video (closed-source)
SEEDANCE_API_KEY=
VEO_API_KEY=
GROK_VIDEO_API_KEY=

# Music (closed-source)
SUNO_API_KEY=
LYRIA_API_KEY=

# Local model paths
ACESTEP_MODEL_PATH=
WAN_MODEL_PATH=

# MinIO
MINIO_ENDPOINT=localhost:9000
MINIO_ACCESS_KEY=minioadmin
MINIO_SECRET_KEY=minioadmin
```

---

## API Reference

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/v1/auth/register` | Register |
| `POST` | `/api/v1/auth/login` | Login (returns JWT) |
| `GET` | `/api/v1/auth/me` | Current user |
| `POST` | `/api/v1/projects` | Create project |
| `GET` | `/api/v1/projects` | List projects |
| `POST` | `/api/v1/projects/{id}/chat` | Chat with AI director (SSE) |
| `POST` | `/api/v1/projects/{id}/generate/image` | Generate image |
| `POST` | `/api/v1/projects/{id}/generate/video` | Generate video clip |
| `POST` | `/api/v1/projects/{id}/generate/music` | Generate music |
| `POST` | `/api/v1/projects/{id}/pipeline/start` | Run full pipeline |
| `POST` | `/api/v1/projects/{id}/compare` | A/B model comparison |
| `POST` | `/api/v1/projects/{id}/export` | Export for platform |
| `GET` | `/api/v1/gallery` | Public gallery |
| `WS` | `/ws/projects/{id}/progress` | Real-time generation progress |

Full Swagger docs at `http://localhost:8000/docs` after starting the backend.

---

## Project Structure

```
aimv-studio/
├── backend/
│   ├── app/
│   │   ├── api/v1/              # REST endpoints
│   │   │   ├── auth.py
│   │   │   ├── project.py
│   │   │   ├── chat.py
│   │   │   ├── generate.py
│   │   │   ├── pipeline.py
│   │   │   ├── compare.py
│   │   │   ├── export.py
│   │   │   └── gallery.py
│   │   ├── core/
│   │   │   ├── agents/          # CrewAI agent definitions + prompts
│   │   │   ├── music_analyzer.py  # librosa / htdemucs / faster-whisper
│   │   │   ├── character_bank.py  # Cross-shot character consistency
│   │   │   ├── shot_router.py     # Sing/story routing + frame chaining
│   │   │   ├── verifier.py        # LLM quality scoring
│   │   │   └── llm_client.py      # OpenAI / Gemini SSE streaming
│   │   ├── adapters/            # One adapter per AI model
│   │   │   ├── base.py
│   │   │   ├── z_image.py
│   │   │   ├── wan_video.py
│   │   │   ├── seedance.py
│   │   │   ├── veo.py
│   │   │   ├── grok_video.py
│   │   │   ├── acestep.py
│   │   │   ├── suno.py
│   │   │   └── lyria.py
│   │   ├── services/
│   │   │   ├── planning_service.py   # MusicAnalyzer → CrewAI crew
│   │   │   ├── generation_service.py # Adapter dispatch + verify-retry loop
│   │   │   └── compose_service.py    # FFmpeg concat / loudnorm / subtitle / export
│   │   ├── workers/
│   │   │   ├── generation_tasks.py   # Celery: image / video / music / compose
│   │   │   └── export_tasks.py       # Celery: platform re-encode
│   │   └── models/              # SQLAlchemy ORM models
│   ├── alembic/                 # DB migrations
│   ├── requirements.txt
│   └── Dockerfile
├── frontend/
│   └── src/
│       ├── views/               # Home / Create / Projects / Gallery / Editor
│       ├── components/          # ComparePanel / SkeletonCard / ...
│       ├── stores/              # Pinia state management
│       └── api/                 # Axios client
├── docker-compose.yml
└── README.md
```

---

## License

MIT
