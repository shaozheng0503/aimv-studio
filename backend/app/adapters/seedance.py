"""Seedance 2.0 video generation adapter — via XiaoYunQue (小云雀) bridge.

XiaoYunQue is a local Flask service that drives the Jianying (剪映) web API
using Playwright + cookie-based auth.  Our adapter proxies generation requests to it.

XiaoYunQue API:
  POST /api/generate-video  (multipart/form-data) → {"task_id": "..."}
  GET  /api/task/{task_id}                        → {"status": ..., "progress": ...}
  GET  /api/video/{task_id}                       → MP4 binary download

Config:
  seedance_base_url  — URL of the running XiaoYunQue service
                       (default: http://localhost:8033)
"""

import asyncio
import os
import tempfile

import httpx

from app.adapters.base import BaseModelAdapter, GenerateRequest, GenerateResult
from app.adapters._poll import poll_until_done
from app.config import get_settings


class SeedanceAdapter(BaseModelAdapter):
    name = "seedance"

    async def generate(self, request: GenerateRequest) -> GenerateResult:
        settings = get_settings()
        base = settings.seedance_base_url.rstrip("/")

        p = request.params or {}
        raw_duration = int(p.get("duration") or 5)
        # XiaoYunQue supports 5 / 10 / 15 s — round up to nearest supported value
        duration = min((d for d in (5, 10, 15) if d >= raw_duration), default=15)
        ratio = p.get("aspect_ratio") or p.get("ratio") or "16:9"
        model = p.get("model", "2.0")  # "fast" (5 credits/s) or "2.0" (8 credits/s)

        form_data = {
            "prompt": request.prompt,
            "duration": str(duration),
            "ratio": ratio,
            "model": model,
        }
        files = None

        async with httpx.AsyncClient(timeout=60) as client:
            # Download reference image and attach as multipart file
            if request.reference_images:
                try:
                    img_resp = await client.get(request.reference_images[0], timeout=30)
                    img_resp.raise_for_status()
                    files = {"image": ("frame.jpg", img_resp.content, "image/jpeg")}
                except Exception:
                    pass  # proceed without reference frame

            resp = await client.post(
                f"{base}/api/generate-video",
                data=form_data,
                files=files,
            )
            resp.raise_for_status()
            data = resp.json()

        task_id = data.get("task_id") or data.get("id", "")
        if not task_id:
            raise ValueError(f"XiaoYunQue did not return a task_id: {data}")

        # Poll until the video is ready
        async with httpx.AsyncClient(timeout=30) as poll_client:
            async def _check() -> tuple[bool, str]:
                r = await poll_client.get(f"{base}/api/task/{task_id}")
                r.raise_for_status()
                d = r.json()
                status = d.get("status", "")
                if status in ("completed", "done"):
                    return True, f"{base}/api/video/{task_id}"
                if status == "failed":
                    raise RuntimeError(
                        f"Seedance task failed: {d.get('error', d.get('message', 'unknown'))}"
                    )
                return False, ""

            download_url = await poll_until_done(_check, interval=5.0, timeout=600.0)

        # Download the MP4 from XiaoYunQue and re-upload to MinIO
        async with httpx.AsyncClient(timeout=120) as dl_client:
            vid_resp = await dl_client.get(download_url)
            vid_resp.raise_for_status()
            video_bytes = vid_resp.content

        loop = asyncio.get_running_loop()
        fd, tmp_path = tempfile.mkstemp(suffix=".mp4")
        try:
            os.write(fd, video_bytes)
            os.close(fd)
            from app.utils.storage import upload_file
            minio_url = await loop.run_in_executor(None, upload_file, tmp_path, "video/mp4")
        finally:
            try:
                os.unlink(tmp_path)
            except OSError:
                pass

        return GenerateResult(
            file_url=minio_url,
            metadata={"model": "seedance-2.0", "task_id": task_id, "duration": duration},
        )
