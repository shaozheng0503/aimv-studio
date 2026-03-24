"""Object storage utilities for MinIO / Aliyun OSS."""

from minio import Minio
from app.config import get_settings
import uuid
from pathlib import Path

# Module-level singletons — created once, reused across uploads.
_minio_client: Minio | None = None
_bucket_ready = False


def get_minio_client() -> Minio:
    global _minio_client
    if _minio_client is None:
        settings = get_settings()
        _minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
        )
    return _minio_client


def ensure_bucket():
    global _bucket_ready
    if _bucket_ready:
        return
    client = get_minio_client()
    settings = get_settings()
    if not client.bucket_exists(settings.minio_bucket):
        client.make_bucket(settings.minio_bucket)
    _bucket_ready = True


def upload_file(local_path: str, content_type: str = "application/octet-stream") -> str:
    """Upload a file to MinIO and return its public URL."""
    settings = get_settings()
    client = get_minio_client()
    ensure_bucket()

    ext = Path(local_path).suffix
    object_name = f"{uuid.uuid4().hex}{ext}"

    client.fput_object(
        settings.minio_bucket,
        object_name,
        local_path,
        content_type=content_type,
    )

    protocol = "https" if settings.minio_secure else "http"
    return f"{protocol}://{settings.minio_endpoint}/{settings.minio_bucket}/{object_name}"


def delete_objects(urls: list[str]) -> None:
    """Delete a list of objects from MinIO given their public URLs. Ignores errors."""
    if not urls:
        return
    settings = get_settings()
    client = get_minio_client()
    prefix = f"/{settings.minio_bucket}/"
    for url in urls:
        try:
            # Extract object name: everything after /<bucket>/
            idx = url.find(prefix)
            if idx == -1:
                continue
            object_name = url[idx + len(prefix):]
            if object_name:
                client.remove_object(settings.minio_bucket, object_name)
        except Exception:
            pass
