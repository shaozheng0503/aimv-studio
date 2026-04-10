"""Object storage utilities for MinIO / Aliyun OSS."""

from minio import Minio
from app.config import get_settings
import uuid
from pathlib import Path
import shutil
from urllib.parse import urlparse
import urllib3

# Module-level singletons — created once, reused across uploads.
_minio_client: Minio | None = None
_minio_http: urllib3.PoolManager | None = None
_bucket_ready = False
_LOCAL_DIR = Path(__file__).resolve().parents[2] / "local_storage"


def _get_minio_http() -> urllib3.PoolManager:
    """Low-timeout, no-retry HTTP client so local fallback triggers quickly."""
    global _minio_http
    if _minio_http is None:
        _minio_http = urllib3.PoolManager(
            timeout=urllib3.Timeout(connect=1.0, read=2.0),
            retries=urllib3.Retry(total=0, connect=0, read=0, redirect=0, status=0),
        )
    return _minio_http


def get_minio_client() -> Minio:
    global _minio_client
    if _minio_client is None:
        settings = get_settings()
        _minio_client = Minio(
            settings.minio_endpoint,
            access_key=settings.minio_access_key,
            secret_key=settings.minio_secret_key,
            secure=settings.minio_secure,
            http_client=_get_minio_http(),
        )
    return _minio_client


def ensure_bucket():
    global _bucket_ready
    if _bucket_ready:
        return
    client = get_minio_client()
    settings = get_settings()
    if not client.bucket_exists(settings.minio_bucket):
        try:
            client.make_bucket(settings.minio_bucket)
        except Exception:
            # Concurrent worker may have already created it; verify it now exists
            if not client.bucket_exists(settings.minio_bucket):
                raise
    _bucket_ready = True


def upload_file(local_path: str, content_type: str = "application/octet-stream") -> str:
    """Upload to MinIO; fall back to local storage if MinIO is unavailable."""
    settings = get_settings()
    ext = Path(local_path).suffix
    object_name = f"{uuid.uuid4().hex}{ext}"
    try:
        client = get_minio_client()
        ensure_bucket()
        client.fput_object(
            settings.minio_bucket,
            object_name,
            local_path,
            content_type=content_type,
        )
        protocol = "https" if settings.minio_secure else "http"
        return f"{protocol}://{settings.minio_endpoint}/{settings.minio_bucket}/{object_name}"
    except Exception:
        _LOCAL_DIR.mkdir(parents=True, exist_ok=True)
        target = _LOCAL_DIR / object_name
        shutil.copy2(local_path, target)
        return f"http://127.0.0.1:8000/storage/{object_name}"


def delete_objects(urls: list[str]) -> None:
    """Delete objects from MinIO/local storage by their URLs. Ignores errors."""
    if not urls:
        return
    settings = get_settings()
    client = get_minio_client()
    prefix = f"/{settings.minio_bucket}/"
    for url in urls:
        try:
            parsed = urlparse(url)
            if parsed.path.startswith("/storage/"):
                filename = Path(parsed.path).name
                local_file = _LOCAL_DIR / filename
                if local_file.exists():
                    local_file.unlink()
                continue
            # Extract object name: everything after /<bucket>/
            idx = url.find(prefix)
            if idx == -1:
                continue
            object_name = url[idx + len(prefix):]
            if object_name:
                client.remove_object(settings.minio_bucket, object_name)
        except Exception:
            pass
