from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    app_name: str = "AIMV"
    debug: bool = False
    cors_origins: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # Database
    database_url: str = "postgresql+asyncpg://aimv:aimv@localhost:5432/aimv"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # Celery
    celery_broker_url: str = "amqp://guest:guest@localhost:5672//"
    celery_result_backend: str = "redis://localhost:6379/1"

    # JWT
    secret_key: str = "aimv-secret-key-change-in-production"
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 1440

    # MinIO / Object Storage
    minio_endpoint: str = "localhost:9000"
    minio_access_key: str = "minioadmin"
    minio_secret_key: str = "minioadmin"
    minio_bucket: str = "aimv-media"
    minio_secure: bool = False

    # Qwen (OpenAI-compatible endpoints)
    qwen_base_url: str = ""          # regular chat, e.g. https://...550w.link
    qwen_model: str = "Qwen/Qwen3.5-9B"
    qwen_reasoning_base_url: str = ""  # reasoning-distilled endpoint
    qwen_reasoning_model: str = "qwopus_9b"   # vLLM alias for Jackrong/Qwen3.5-9B-Claude-4.6-Opus-Reasoning-Distilled

    # AI Model API Keys
    openai_api_key: str = ""
    gemini_api_key: str = ""
    suno_api_key: str = ""
    lyria_api_key: str = ""
    seedance_api_key: str = ""
    seedance_base_url: str = "http://localhost:8033"  # XiaoYunQue bridge service
    veo_api_key: str = ""
    grok_video_api_key: str = ""
    z_image_api_key: str = ""
    z_image_base_url: str = "http://localhost:7860"

    # Google Cloud service account (for gemini-image / imagen-3.0 / veo)
    # Priority: google_sa_json (inline JSON string) > google_sa_path (file)
    # Set GOOGLE_SA_JSON=<full JSON string> in env to avoid relying on a mounted file.
    google_sa_path: str = ".credentials/gcp-sa.json"
    google_sa_json: str = ""  # full SA JSON as a single-line string (optional)

    # Local model server base URLs (override via env vars in production)
    acestep_base_url: str = "http://localhost:7860"
    wan_video_base_url: str = "http://localhost:8188"

    # Local model paths
    acestep_model_path: str = ""
    wan_model_path: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
