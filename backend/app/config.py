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

    # AI Model API Keys
    openai_api_key: str = ""
    gemini_api_key: str = ""
    suno_api_key: str = ""
    lyria_api_key: str = ""
    seedance_api_key: str = ""
    veo_api_key: str = ""
    grok_video_api_key: str = ""
    z_image_api_key: str = ""
    z_image_base_url: str = "http://localhost:7860"

    # Local model server base URLs
    acestep_base_url: str = "http://localhost:7860"
    wan_video_base_url: str = "http://localhost:8188"

    # Local model paths
    acestep_model_path: str = ""
    wan_model_path: str = ""

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


@lru_cache
def get_settings() -> Settings:
    return Settings()
