"""Mock pipeline runner for demo recording.

Activated by AIMV_MOCK_PIPELINE=1 in .env.

Replays a full pipeline run using pre-existing media files from a source
project, pushing real Redis progress events so the frontend WebSocket
animates exactly like a live generation.

Timeline (total ~22s visible generation):
  T+0    pipeline.started
  T+0.5  music running
  T+3    music completed
  T+3.2  image tasks (silent — images not shown in ProgressPanel)
  T+4    video 1 running  (segment 1, pct 0)
  T+5.2  video 1 running  (pct 65)
  T+6.5  video 1 completed (with file_url + thumbnail)
  ... each video 2.5s, 7 total = 17.5s
  T+22   compose running
  T+24.5 compose completed (final video url)
  T+25   pipeline.completed → frontend shows "你的 MV 已完成!"
"""

from __future__ import annotations

import asyncio
import json
import os
import random

import redis.asyncio as aioredis

# ─── Exported constants (used by mock chat endpoint) ─────────────────────────

# Only 3 scenes for demo — keeps recording to ~20s generation time
_MOCK_STORYBOARD = [
    {
        "index": 0, "label": "凝视",
        "start_time": 40.0, "end_time": 80.0, "duration": 40.0,
        "description": "特写：短发女主角 EIKO 睁开双眼，苍白皮肤，瞳孔映出冷白光",
        "image_prompt": "extreme close-up of a young woman with black bob hair and pale porcelain skin, piercing grey eyes slowly opening, subtle neon reflections in pupils, cinematic shallow depth of field, EIKO aesthetic",
        "video_prompt": "ultra close-up, eyes slowly opening, micro-expressions, shallow DoF, cinematic color grade",
        "negative_prompt": "blurry, low-res, deformed, watermark",
        "camera_direction": "static_closeup",
        "characters": ["EIKO"],
        "model_recommendation": "veo-3.1",
    },
    {
        "index": 1, "label": "流水线",
        "start_time": 80.0, "end_time": 130.0, "duration": 50.0,
        "description": "巨大地下工厂传送带，扑克牌工卡源源不断被生产，两侧隧道走过无数扑克头工人",
        "image_prompt": "massive subterranean factory, long conveyor belt producing endless playing cards, two side tunnels with faceless pillow-headed workers walking in lockstep, industrial metal, warm spot lights, cinematic wide angle, surreal dystopian",
        "video_prompt": "overhead tracking shot following the conveyor belt, workers marching in the side tunnels, mechanical rhythm",
        "negative_prompt": "blurry, text, watermark",
        "camera_direction": "overhead_tracking",
        "characters": ["扑克人群像"],
        "model_recommendation": "veo-3.1",
    },
    {
        "index": 2, "label": "炸弹",
        "start_time": 130.0, "end_time": 165.0, "duration": 35.0,
        "description": "监控摄像头视角：EIKO 背对镜头在空旷办公室放置装置，扑克A缓缓倒计时",
        "image_prompt": "CCTV fish-eye view of a sparse open-plan office, young woman with black bob hair viewed from behind placing a small device on a desk, playing card Ace displayed on multiple screens counting down, cold fluorescent light, surveillance camera grain",
        "video_prompt": "CCTV fish-eye wide angle, protagonist moving slowly, screens flickering with playing card countdown, tension building",
        "negative_prompt": "blurry, watermark",
        "camera_direction": "fisheye_cctv",
        "characters": ["EIKO"],
        "model_recommendation": "grok-video-1",
    },
    {
        "index": 3, "label": "崩塌",
        "start_time": 165.0, "end_time": 210.0, "duration": 45.0,
        "description": "办公室内部爆炸崩塌，桌椅卷入碎片风暴，扑克牌如雪花四散",
        "image_prompt": "interior of an office mid-explosion, desks and chairs flying apart in a debris storm, hundreds of playing cards scattered like snowflakes, dramatic dynamic angles, cinematic slow-motion",
        "video_prompt": "slow-motion explosion, office furniture debris, playing cards flying everywhere, dramatic camera shake",
        "negative_prompt": "static, watermark",
        "camera_direction": "dynamic_handheld",
        "characters": ["扑克人群像"],
        "model_recommendation": "seedance-2.0",
    },
    {
        "index": 4, "label": "逃离",
        "start_time": 210.0, "end_time": 240.0, "duration": 30.0,
        "description": "EIKO 在狭窄走廊中奔跑，两侧白色门框透出强光，身体留下粒子拖尾",
        "image_prompt": "young woman with black bob hair running through a narrow dark corridor, strong backlight from white doorways on both sides, particle trails around her silhouette, dynamic motion, cinematic",
        "video_prompt": "side-tracking shot, protagonist running, strong backlight, particle trails, motion blur",
        "negative_prompt": "static, blurry, watermark",
        "camera_direction": "side_tracking",
        "characters": ["EIKO"],
        "model_recommendation": "veo-3.1",
    },
    {
        "index": 5, "label": "虚空",
        "start_time": 240.0, "end_time": 252.0, "duration": 12.0,
        "description": "EIKO 站在深红虚空中，四周漂浮被撕碎的扑克牌残片，衣角飘动",
        "image_prompt": "young woman with black bob hair standing in a deep crimson void, torn playing card fragments floating around her, coat edges billowing in slow motion, surreal cinematic composition",
        "video_prompt": "floating card fragments, slow motion fabric movement, ethereal red void atmosphere",
        "negative_prompt": "blurry, noisy, watermark",
        "camera_direction": "slow_orbit",
        "characters": ["EIKO"],
        "model_recommendation": "veo-3.1",
    },
    {
        "index": 6, "label": "标志",
        "start_time": 252.0, "end_time": 258.7, "duration": 6.7,
        "description": "黑底白字 EIKO 徽标渐现，配合最后一击音效定格",
        "image_prompt": "minimalist title card, bold white gothic lettering EIKO on pure black background, subtle embossed playing card texture, dramatic fade in",
        "video_prompt": "title card fade in with subtle grain, final frame freeze",
        "negative_prompt": "colorful, busy, watermark",
        "camera_direction": "static",
        "characters": [],
        "model_recommendation": "veo-3.1",
    },
]

_MOCK_CHARACTER_BANK = {
    "EIKO": {
        "name": "EIKO",
        "description": "觉醒的短发少女，苍白皮肤、灰色眼眸，身穿暗色赛博剪裁西装",
        "appearance": "black bob hair, pale porcelain skin, piercing grey eyes, dark cyber-tailored suit",
        "lora_id": "eiko_character_v1",
        "gender": "female",
    },
    "扑克人群像": {
        "name": "扑克人群像",
        "description": "头部被扑克花色抱枕取代的无面工人群体，代表失去个性的社会机器",
        "appearance": "faceless office workers with playing-card suit pillows covering their heads",
        "lora_id": "card_suit_worker_v1",
        "gender": "neutral",
    },
}

_MOCK_MUSIC_PLAN = {
    "music_prompt": "dark cinematic synth, slow pulsing bass, rising tension into cathartic release, hybrid orchestral-electronic score, 92 bpm",
    "bpm": 92,
    "needs_vocal": True,
    "lyrics_theme": "白天拼演技 晚上备戏码\n说着要感恩工资发放\n计时器推倒最后的墙\n观点被同化 创意被抹杀",
    "model_recommendation": "suno-v4",
    "genre": "cinematic electronic",
}


async def run_mock_pipeline(project_id: int) -> None:
    """Async entry-point — call via asyncio.create_task from pipeline endpoint."""
    from app.config import get_settings
    from app.core.database import async_session
    from app.models.project import Media, Project, Task

    settings = get_settings()
    source_project_id = int(settings.aimv_mock_source_project or "20")

    # Gather source media by type + sort_order
    async with async_session() as db:
        from sqlalchemy import select

        result = await db.execute(
            select(Media)
            .where(Media.project_id == source_project_id)
            .order_by(Media.sort_order)
        )
        src_media = result.scalars().all()
        # Read project storyboard so we can emit proper labels/models
        proj_res = await db.execute(select(Project).where(Project.id == project_id))
        project = proj_res.scalar_one_or_none()
        storyboard = project.storyboard or [] if project else []

    audio_url = next((m.file_url for m in src_media if m.type == "music"), "")
    image_urls = [m.file_url for m in sorted(
        (m for m in src_media if m.type == "image"), key=lambda m: m.sort_order)]
    image_thumbs = [
        (m.metadata_json or {}).get("thumbnail_url", m.file_url)
        for m in sorted((m for m in src_media if m.type == "image"), key=lambda m: m.sort_order)
    ]
    clip_urls = [m.file_url for m in sorted(
        (m for m in src_media if m.type == "video" and m.sort_order < 90),
        key=lambda m: m.sort_order,
    )]
    clip_thumbs = [
        (m.metadata_json or {}).get("thumbnail_url", "")
        for m in sorted(
            (m for m in src_media if m.type == "video" and m.sort_order < 90),
            key=lambda m: m.sort_order,
        )
    ]
    final_url = next(
        (m.file_url for m in src_media if m.type == "final_video"), clip_urls[0] if clip_urls else ""
    )

    # Use all 7 scenes for a fuller demo
    _DEMO_SCENE_INDICES = [0, 1, 2, 3, 4, 5, 6]
    n_scenes = min(7, len(storyboard), len(clip_urls))
    storyboard = storyboard[:n_scenes]
    # Remap clip/image URLs to match the 3 demo scenes
    clip_urls = [clip_urls[i] if i < len(clip_urls) else clip_urls[-1] for i in _DEMO_SCENE_INDICES[:n_scenes]]
    clip_thumbs = [clip_thumbs[i] if i < len(clip_thumbs) else "" for i in _DEMO_SCENE_INDICES[:n_scenes]]
    image_urls = [image_urls[i] if i < len(image_urls) else image_urls[-1] for i in _DEMO_SCENE_INDICES[:n_scenes]]

    r = aioredis.from_url(settings.redis_url)
    channel = f"project:{project_id}:progress"

    async def pub(payload: dict) -> None:
        await r.publish(channel, json.dumps(payload))

    try:
        # ── pipeline started ──────────────────────────────────────
        await pub({"type": "pipeline", "status": "started", "task_id": 0,
                   "total_segments": n_scenes})
        await asyncio.sleep(0.5)

        # ── music running → completed ─────────────────────────────
        await pub({"type": "music", "status": "running", "task_id": 0})
        await asyncio.sleep(4.5)

        # Insert music Task + Media in DB
        music_task_id, music_media_id = await _create_task_and_media(
            project_id,
            task_type="music",
            model_name="suno-v4",
            params={"prompt": "dark cinematic synth 92bpm", "duration": 258.7},
            result={"file_url": audio_url, "quality_score": 0.91, "duration": 258.7},
            media_type="music",
            file_url=audio_url,
            duration=258.7,
        )
        await pub({"type": "music", "status": "completed", "task_id": music_task_id,
                   "file_url": audio_url})
        await asyncio.sleep(0.2)

        # ── image tasks (silent — not shown in ProgressPanel) ────
        for i in range(n_scenes):
            seg = storyboard[i] if i < len(storyboard) else {}
            await _create_task_and_media(
                project_id,
                task_type="image",
                model_name="gemini-image",
                params={"prompt": seg.get("image_prompt", ""), "sort_order": i},
                result={"file_url": image_urls[i] if i < len(image_urls) else ""},
                media_type="image",
                file_url=image_urls[i] if i < len(image_urls) else "",
                duration=None,
                sort_order=i,
            )
            await asyncio.sleep(0.08)
        await asyncio.sleep(0.5)

        # ── video tasks (sequential, 2.5s each) ──────────────────
        for i in range(n_scenes):
            seg = storyboard[i] if i < len(storyboard) else {}
            model = seg.get("model_recommendation", "veo-3.1")
            label = seg.get("label", f"片段{i+1}")
            clip_url = clip_urls[i] if i < len(clip_urls) else final_url
            thumb = clip_thumbs[i] if i < len(clip_thumbs) else ""

            await pub({"type": "video", "status": "running", "task_id": 0,
                       "segment": i + 1, "total": n_scenes, "pct": 0,
                       "label": label, "model": model})
            await asyncio.sleep(2.5)
            await pub({"type": "video", "status": "running", "task_id": 0,
                       "segment": i + 1, "total": n_scenes, "pct": 65,
                       "label": label, "model": model})
            await asyncio.sleep(2.5)

            vt_id, _ = await _create_task_and_media(
                project_id,
                task_type="video",
                model_name=model,
                params={"prompt": seg.get("video_prompt", ""), "sort_order": i},
                result={"file_url": clip_url, "quality_score": round(random.uniform(0.83, 0.93), 3),
                        "thumbnail_url": thumb},
                media_type="video",
                file_url=clip_url,
                duration=(seg.get("end_time", 0) - seg.get("start_time", 0)) or 30.0,
                sort_order=i,
            )
            await pub({"type": "video", "status": "completed", "task_id": vt_id,
                       "segment": i + 1, "file_url": clip_url, "thumbnail_url": thumb})
            await asyncio.sleep(0.1)

        # ── compose ───────────────────────────────────────────────
        await pub({"type": "compose", "status": "running", "task_id": 0,
                   "clips": n_scenes, "has_audio": bool(audio_url)})
        await asyncio.sleep(5.0)

        ct_id, _ = await _create_task_and_media(
            project_id,
            task_type="compose",
            model_name="ffmpeg",
            params={"video_paths": clip_urls[:n_scenes], "audio_path": audio_url},
            result={"file_url": final_url, "composed": True, "segments": n_scenes},
            media_type="final_video",
            file_url=final_url,
            duration=258.7,
        )
        await pub({"type": "compose", "status": "completed", "task_id": ct_id,
                   "file_url": final_url})
        await asyncio.sleep(0.5)

        # ── mark project done ─────────────────────────────────────
        await _set_project_done(project_id, final_url)
        # Update canvas nodes with real videoUrl + status=done so canvas view shows thumbnails
        await _update_canvas_nodes(project_id, clip_urls[:n_scenes], clip_thumbs[:n_scenes])
        await pub({"type": "pipeline", "status": "completed", "task_id": 0,
                   "video_count": n_scenes, "has_audio": bool(audio_url)})

    finally:
        await r.aclose()


async def _create_task_and_media(
    project_id: int,
    task_type: str,
    model_name: str,
    params: dict,
    result: dict,
    media_type: str,
    file_url: str,
    duration: float | None,
    sort_order: int = 0,
) -> tuple[int, int]:
    from app.core.database import async_session
    from app.models.project import Media, Task

    async with async_session() as db:
        task = Task(
            project_id=project_id,
            type=task_type,
            model_name=model_name,
            status="completed",
            params=params,
            result=result,
            quality_score=result.get("quality_score"),
            retry_count=0,
        )
        db.add(task)
        await db.flush()

        media = Media(
            project_id=project_id,
            task_id=task.id,
            type=media_type,
            file_url=file_url,
            duration=duration,
            metadata_json=result,
            sort_order=sort_order,
        )
        db.add(media)
        await db.commit()
        await db.refresh(task)
        await db.refresh(media)
        return task.id, media.id


async def _set_project_done(project_id: int, final_url: str) -> None:
    from app.core.database import async_session
    from app.models.project import Media, Project
    from sqlalchemy import select

    async with async_session() as db:
        result = await db.execute(select(Project).where(Project.id == project_id))
        project = result.scalar_one_or_none()
        if project:
            project.status = "done"
            # Add video alias so all frontend views find the final video
            existing = await db.execute(
                select(Media).where(
                    Media.project_id == project_id,
                    Media.type == "video",
                    Media.sort_order == 99,
                )
            )
            if not existing.scalar_one_or_none():
                db.add(Media(
                    project_id=project_id,
                    type="video",
                    file_url=final_url,
                    duration=258.7,
                    metadata_json={"is_final": True, "composed": True},
                    sort_order=99,
                ))
            await db.commit()


async def _update_canvas_nodes(project_id: int, clip_urls: list, clip_thumbs: list) -> None:
    """After pipeline finishes, backfill canvas shot nodes with real videoUrl + status=done."""
    from app.core.database import async_session
    from app.models.canvas import Canvas
    from sqlalchemy import select
    from sqlalchemy.orm.attributes import flag_modified

    async with async_session() as db:
        result = await db.execute(select(Canvas).where(Canvas.project_id == project_id))
        canvas = result.scalar_one_or_none()
        if not canvas or not canvas.nodes:
            return
        updated = []
        shot_idx = 0
        for node in canvas.nodes:
            if node.get("type") == "shot":
                node = dict(node)
                data = dict(node.get("data", {}))
                if shot_idx < len(clip_urls):
                    data["videoUrl"] = clip_urls[shot_idx]
                data["status"] = "done"
                node["data"] = data
                shot_idx += 1
            updated.append(node)
        canvas.nodes = updated
        flag_modified(canvas, "nodes")
        await db.commit()
