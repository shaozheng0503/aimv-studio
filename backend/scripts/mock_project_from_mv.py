"""Fabricate a complete AIMV pipeline run from an existing MV.

Splits the source video into N scene clips, extracts per-scene first-frame
images, middle-frame thumbnails, and the audio track. Uploads everything to
local_storage/ and inserts Project + Task + Media + Canvas rows so the
backend looks as if the full pipeline ran end-to-end.

Usage:
  cd backend
  .venv/bin/python -m scripts.mock_project_from_mv \
      --video /path/to/source.mp4 \
      --title "觉醒协议 · Wake Protocol"
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timedelta
from pathlib import Path

THIS_DIR = Path(__file__).resolve().parent
BACKEND_DIR = THIS_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.models.canvas import Canvas, CanvasShot
from app.models.project import Media, Project, Task
from app.models.user import User

LOCAL_STORAGE = BACKEND_DIR / "local_storage"
STORAGE_URL = "http://127.0.0.1:8000/storage"


# ─── Story design (hand-authored to match the source MV's theme) ─────────────

SCENES = [
    {
        "label": "觉醒前夜",
        "start_time": 0.0,
        "end_time": 40.0,
        "description": "黄昏的开放式办公室，日光灯冷白，工位上坐着一排排头被扑克牌花色抱枕覆盖的工人，所有人整齐划一地敲键盘",
        "image_prompt": "cinematic wide shot, dim corporate office at dusk, rows of identical workers seated at desks, each worker's head replaced by a plush pillow printed with a playing-card suit (spades, hearts), cold fluorescent light, muted teal and slate palette, volumetric haze, highly detailed, film still, anamorphic lens",
        "video_prompt": "slow dolly-in through rows of faceless card-suit workers, papers still, subtle fluorescent flicker, cold cinematic grade",
        "negative_prompt": "blurry, cartoon, low-res, text, logos",
        "camera_direction": "dolly_in",
        "characters": ["扑克人群像"],
        "video_model": "veo-3.1",
    },
    {
        "label": "凝视",
        "start_time": 40.0,
        "end_time": 80.0,
        "description": "特写：短发女主角 EIKO 睁开双眼，瞳孔映出冷白光，苍白皮肤，嘴唇紧闭，背景虚化的霓虹灯",
        "image_prompt": "extreme close-up of a young woman with black bob hair and pale porcelain skin, piercing grey eyes slowly opening, subtle neon reflections in pupils, cinematic shallow depth of field, soft rim light, EIKO aesthetic",
        "video_prompt": "ultra close-up, eyes slowly opening, micro-expressions, shallow DoF, cinematic color grade",
        "negative_prompt": "blurry, low-res, deformed, watermark",
        "camera_direction": "static_closeup",
        "characters": ["EIKO"],
        "video_model": "veo-3.1",
    },
    {
        "label": "流水线",
        "start_time": 80.0,
        "end_time": 130.0,
        "description": "巨大的地下工厂传送带，印有扑克花色的工卡源源不断被生产出来，两侧隧道里走过无数个扑克抱枕头的工人",
        "image_prompt": "massive subterranean factory, long conveyor belt producing endless sheets of playing cards, two side tunnels with faceless pillow-headed workers walking in lockstep, industrial metal, warm spot lights, cinematic wide angle, surreal dystopian",
        "video_prompt": "overhead tracking shot following the conveyor belt, workers marching in the side tunnels, mechanical rhythm",
        "negative_prompt": "blurry, text, sign, watermark",
        "camera_direction": "overhead_tracking",
        "characters": ["扑克人群像"],
        "video_model": "veo-3.1",
    },
    {
        "label": "监视",
        "start_time": 130.0,
        "end_time": 170.0,
        "description": "低分辨率 CCTV 监控画面，空无一人的蓝色卫生间，一个红色定时炸弹贴在墙角，数字跳动",
        "image_prompt": "low-res CCTV surveillance shot of an empty blue public restroom, wall-mounted timer device with red LED countdown 00:59, timestamp overlay 09/04/2024 09:01, CAMERA ID 100, gritty VHS noise, teal shadows",
        "video_prompt": "security-cam style shaky handheld, timer counting down, subtle vhs tracking artefacts",
        "negative_prompt": "high-res, clean, colorful",
        "camera_direction": "cctv_fixed",
        "characters": [],
        "video_model": "grok-video-1",
    },
    {
        "label": "爆破",
        "start_time": 170.0,
        "end_time": 210.0,
        "description": "办公室瞬间被冲击波掀翻，纸张飞舞，红色应急灯亮起，电脑桌椅翻倒，烟雾弥漫",
        "image_prompt": "instant office explosion aftermath, papers flying mid-air frozen in time, overturned chairs and monitors, red emergency strobe lights cutting through smoke, dramatic side light, cinematic action still",
        "video_prompt": "shockwave pushes outward from center, papers explode into the air, red emergency strobe cuts through the haze",
        "negative_prompt": "cartoon, blurry, text",
        "camera_direction": "shockwave_push",
        "characters": [],
        "video_model": "seedance-2.0",
    },
    {
        "label": "逃离",
        "start_time": 210.0,
        "end_time": 240.0,
        "description": "EIKO 在狭窄走廊中奔跑，两侧白色门框透出强光，身体留下微小粒子拖尾",
        "image_prompt": "young woman with black bob hair running through a narrow dark corridor, strong backlight from white doorways on both sides, particle trails around her silhouette, dynamic motion, cinematic",
        "video_prompt": "side-tracking shot, protagonist running, strong backlight, particle trails, motion blur",
        "negative_prompt": "static, blurry, watermark",
        "camera_direction": "side_tracking",
        "characters": ["EIKO"],
        "video_model": "veo-3.1",
    },
    {
        "label": "自由",
        "start_time": 240.0,
        "end_time": 258.7,
        "description": "EIKO 独立站在一片纯粹红色空间中央，镜头缓慢拉远，最终化为 EIKO LOGO 的黑底白字",
        "image_prompt": "lone figure standing at center of an infinite red void, camera slowly pulling back, minimalist, cinematic, ends with black background and white EIKO logo text",
        "video_prompt": "slow dolly-out from overhead, figure becomes a dot, fade to black logo reveal",
        "negative_prompt": "cluttered, busy, text",
        "camera_direction": "dolly_out",
        "characters": ["EIKO"],
        "video_model": "veo-3.1",
    },
]

CHARACTER_BANK = {
    "EIKO": {
        "name": "EIKO",
        "description": "觉醒的短发少女，苍白皮肤、灰色眼眸，身穿暗色赛博剪裁西装，象征未被同化的创造力",
        "appearance": "black bob hair, pale porcelain skin, piercing grey eyes, dark cyber-tailored suit with structured collar",
        "lora_id": "eiko_character_v1",
        "gender": "female",
    },
    "扑克人群像": {
        "name": "扑克人群像",
        "description": "头部被扑克牌花色抱枕取代的无面工人群体，代表失去个性的社会机器",
        "appearance": "faceless office workers with oversized playing-card suit pillows (spade, heart, diamond, club) covering their heads, business attire",
        "lora_id": "card_suit_worker_v1",
        "gender": "neutral",
    },
}

MUSIC_PLAN = {
    "music_prompt": "dark cinematic synth, slow pulsing bass, rising tension into cathartic release, hybrid orchestral-electronic score, 92 bpm",
    "bpm": 92,
    "needs_vocal": True,
    "lyrics_theme": (
        "白天拼演技 晚上备戏码\n"
        "说着要感恩工资发放\n"
        "计时器推倒最后的墙\n"
        "观点被同化 创意被抹杀\n"
        "—— 我们是活着的牌，不是被发的手"
    ),
    "model_recommendation": "suno-v4",
    "genre": "cinematic electronic",
}

CHAT_HISTORY = [
    {
        "role": "user",
        "content": "我想做一部暗黑向的觉醒 MV，主角是个短发少女，对抗一个所有人都被同化的扑克牌社会。258 秒左右，赛博电影感。",
    },
    {
        "role": "assistant",
        "content": (
            "主题抓得很好，我把它拆成三幕：**同化 → 引爆 → 觉醒**。\n\n"
            "- **第一幕（0–130s）**：办公室里的扑克人群像，以及女主角 EIKO 的第一次凝视觉醒\n"
            "- **第二幕（130–210s）**：CCTV 引入倒计时炸弹，办公室被冲击波掀翻\n"
            "- **第三幕（210–258s）**：EIKO 穿越走廊逃离，最终站在红色虚空中\n\n"
            "音乐我会用 Suno 生成 92 BPM 的暗调 synth-cinematic，带人声，歌词围绕 *「活着的牌」* 这一 metaphor。确认一下这个结构？"
        ),
    },
    {
        "role": "user",
        "content": "就按这个来。人物细节一定要到位，镜头语言要电影感，7 个镜头都要有独立的情绪。",
    },
    {
        "role": "assistant",
        "content": (
            "收到 ✅ 我已经准备好完整分镜方案：\n\n"
            "1. 觉醒前夜（dolly-in 办公室群像，冷白日光灯）\n"
            "2. 凝视（EIKO 眼部特写，瞳孔反射霓虹）\n"
            "3. 流水线（地下工厂传送带俯拍）\n"
            "4. 监视（CCTV 炸弹倒计时）\n"
            "5. 爆破（冲击波扩散，红光应急灯）\n"
            "6. 逃离（侧向跟拍奔跑）\n"
            "7. 自由（dolly-out + EIKO LOGO）\n\n"
            "模型路由：人物特写用 **Veo 3.1**、监控/CCTV 用 **Grok Video 1**、爆破动作用 **Seedance 2.0**，音乐用 **Suno v4**。\n"
            "点击「开始生成」我就启动完整流水线。"
        ),
    },
]


# ─── FFmpeg helpers ──────────────────────────────────────────────────────────

def ffmpeg(args: list[str]) -> None:
    subprocess.run(args, check=True, capture_output=True)


def split_clip(src: str, start: float, end: float, dst: str) -> None:
    ffmpeg([
        "ffmpeg", "-y", "-ss", f"{start:.3f}", "-to", f"{end:.3f}",
        "-i", src, "-c:v", "libx264", "-preset", "fast", "-crf", "20",
        "-c:a", "aac", "-b:a", "160k", dst,
    ])


def extract_audio(src: str, dst: str) -> None:
    ffmpeg(["ffmpeg", "-y", "-i", src, "-vn", "-c:a", "aac", "-b:a", "192k", dst])


def extract_frame(src: str, ts: float, dst: str) -> None:
    ffmpeg([
        "ffmpeg", "-y", "-ss", f"{ts:.3f}", "-i", src,
        "-frames:v", "1", "-q:v", "2", "-vf", "scale=1280:-2", dst,
    ])


# ─── Storage helpers ─────────────────────────────────────────────────────────

def stash(path: Path) -> str:
    """Move/copy a file into local_storage/ with a uuid name, return the public URL."""
    LOCAL_STORAGE.mkdir(parents=True, exist_ok=True)
    name = f"{uuid.uuid4().hex}{path.suffix}"
    dst = LOCAL_STORAGE / name
    shutil.copy2(path, dst)
    return f"{STORAGE_URL}/{name}"


# ─── DB helpers ──────────────────────────────────────────────────────────────

def get_sync_engine():
    s = get_settings()
    sync_url = s.database_url.replace("+asyncpg", "+psycopg2").replace(
        "postgresql+asyncpg", "postgresql"
    )
    return create_engine(sync_url)


def set_timestamps(db, table: str, row_id: int, created_at: datetime):
    db.execute(
        text(f"UPDATE {table} SET created_at = :ca, updated_at = :ua WHERE id = :i"),
        {"ca": created_at, "ua": created_at, "i": row_id},
    )


def get_or_create_demo_user(db) -> int:
    from app.core.security import hash_password
    row = db.execute(text("SELECT id FROM users WHERE username = 'demo'")).fetchone()
    if row:
        return row[0]
    user = User(username="demo", email="demo@aimv.local", password_hash=hash_password("demo123"))
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.id


def delete_existing_project(db, user_id: int, title: str):
    rows = db.execute(
        text("SELECT id FROM projects WHERE user_id = :u AND title = :t"),
        {"u": user_id, "t": title},
    ).fetchall()
    for (pid,) in rows:
        # cascade via ORM relationships
        proj = db.get(Project, pid)
        if proj:
            db.delete(proj)
    db.commit()


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--video", required=True, help="Absolute path to source MV")
    ap.add_argument("--title", default="觉醒协议 · Wake Protocol")
    args = ap.parse_args()

    src = Path(args.video).resolve()
    assert src.exists(), f"Source video not found: {src}"

    work = Path("/tmp") / f"aimv_mock_{uuid.uuid4().hex[:8]}"
    work.mkdir(parents=True, exist_ok=True)
    print(f"[work] {work}")

    print("[ffmpeg] extracting audio track …")
    audio_local = work / "track.m4a"
    extract_audio(str(src), str(audio_local))

    print(f"[ffmpeg] splitting source into {len(SCENES)} scene clips …")
    clip_paths: list[Path] = []
    first_frame_paths: list[Path] = []
    thumb_paths: list[Path] = []
    for i, sc in enumerate(SCENES):
        clip = work / f"clip_{i+1:02d}.mp4"
        split_clip(str(src), sc["start_time"], sc["end_time"], str(clip))
        clip_paths.append(clip)

        ff = work / f"first_{i+1:02d}.jpg"
        extract_frame(str(src), sc["start_time"] + 0.2, str(ff))
        first_frame_paths.append(ff)

        mid = (sc["start_time"] + sc["end_time"]) / 2
        tb = work / f"thumb_{i+1:02d}.jpg"
        extract_frame(str(src), mid, str(tb))
        thumb_paths.append(tb)

    print("[storage] copying to local_storage …")
    audio_url = stash(audio_local)
    clip_urls = [stash(p) for p in clip_paths]
    image_urls = [stash(p) for p in first_frame_paths]
    thumb_urls = [stash(p) for p in thumb_paths]
    final_video_url = stash(src)  # The final product = the source MV itself

    engine = get_sync_engine()
    Session = sessionmaker(bind=engine)

    with Session() as db:
        user_id = get_or_create_demo_user(db)
        delete_existing_project(db, user_id, args.title)

        now = datetime.utcnow()
        t0 = now - timedelta(minutes=14)  # Project created 14 min ago

        # ── Project ────────────────────────────────────────────────
        project = Project(
            user_id=user_id,
            title=args.title,
            status="done",
            visual_style="cinematic dystopian",
            music_style="cinematic electronic",
            mood="awakening",
            chat_history=CHAT_HISTORY,
            storyboard=[{
                "index": i,
                "label": s["label"],
                "start_time": s["start_time"],
                "end_time": s["end_time"],
                "duration": s["end_time"] - s["start_time"],
                "description": s["description"],
                "image_prompt": s["image_prompt"],
                "video_prompt": s["video_prompt"],
                "negative_prompt": s["negative_prompt"],
                "camera_direction": s["camera_direction"],
                "characters": s["characters"],
                "model_recommendation": s["video_model"],
            } for i, s in enumerate(SCENES)],
            character_bank=CHARACTER_BANK,
            style_config={
                "music_plan": MUSIC_PLAN,
                "theme": "觉醒 vs 同化",
                "published": True,
            },
            model_preferences={
                "image": "gemini-image",
                "video": "veo-3.1",
                "music": "suno-v4",
            },
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        set_timestamps(db, "projects", project.id, t0)

        # ── Phase 1 : image tasks + music task (parallel) ──────────
        image_tasks: list[Task] = []
        for i, s in enumerate(SCENES):
            img_t = Task(
                project_id=project.id,
                type="image",
                model_name="gemini-image",
                status="completed",
                params={
                    "prompt": s["image_prompt"],
                    "negative_prompt": s["negative_prompt"],
                    "character_name": (s["characters"] or [""])[0],
                },
                result={
                    "file_url": image_urls[i],
                    "quality_score": round(random.uniform(0.84, 0.94), 3),
                    "model": "gemini-image",
                    "seed": random.randint(100000, 999999),
                },
                quality_score=round(random.uniform(0.84, 0.94), 3),
                retry_count=0,
            )
            db.add(img_t)
            db.flush()
            image_tasks.append(img_t)

        music_task = Task(
            project_id=project.id,
            type="music",
            model_name="suno-v4",
            status="completed",
            params={
                "prompt": MUSIC_PLAN["music_prompt"],
                "bpm": MUSIC_PLAN["bpm"],
                "duration": 258.7,
                "instrumental": not MUSIC_PLAN["needs_vocal"],
                "lyrics": MUSIC_PLAN["lyrics_theme"],
                "genre": MUSIC_PLAN["genre"],
            },
            result={
                "file_url": audio_url,
                "quality_score": 0.91,
                "model": "suno-v4",
                "duration": 258.7,
            },
            quality_score=0.91,
            retry_count=0,
        )
        db.add(music_task)
        db.flush()

        db.commit()

        # Timestamps: images 20s–70s, music 40s–95s after project create
        for i, t in enumerate(image_tasks):
            set_timestamps(db, "tasks", t.id, t0 + timedelta(seconds=20 + i * 5))
        set_timestamps(db, "tasks", music_task.id, t0 + timedelta(seconds=95))

        # Image media
        for i, t in enumerate(image_tasks):
            m = Media(
                project_id=project.id, task_id=t.id,
                type="image",
                file_url=image_urls[i],
                duration=None,
                metadata_json={
                    "scene_label": SCENES[i]["label"],
                    "scene_index": i,
                    "prompt": SCENES[i]["image_prompt"],
                    "thumbnail_url": thumb_urls[i],
                },
                sort_order=i,
            )
            db.add(m)
            db.flush()
            set_timestamps(db, "media", m.id, t0 + timedelta(seconds=20 + i * 5))

        # Music media
        music_media = Media(
            project_id=project.id, task_id=music_task.id,
            type="music",
            file_url=audio_url,
            duration=258.7,
            metadata_json={
                "bpm": MUSIC_PLAN["bpm"],
                "lyrics": MUSIC_PLAN["lyrics_theme"],
                "genre": MUSIC_PLAN["genre"],
                "model": "suno-v4",
            },
            sort_order=0,
        )
        db.add(music_media)
        db.flush()
        set_timestamps(db, "media", music_media.id, t0 + timedelta(seconds=95))

        db.commit()

        # ── Phase 2 : video tasks (sequential, ~40s each) ──────────
        video_tasks: list[Task] = []
        video_media_rows: list[Media] = []
        for i, s in enumerate(SCENES):
            vt = Task(
                project_id=project.id,
                type="video",
                model_name=s["video_model"],
                status="completed",
                params={
                    "prompt": s["video_prompt"],
                    "negative_prompt": s["negative_prompt"],
                    "character_name": (s["characters"] or [""])[0],
                    "first_frame_image": image_urls[i],
                    "duration": s["end_time"] - s["start_time"],
                    "label": s["label"],
                    "camera_direction": s["camera_direction"],
                },
                result={
                    "file_url": clip_urls[i],
                    "quality_score": round(random.uniform(0.82, 0.93), 3),
                    "thumbnail_url": thumb_urls[i],
                    "model": s["video_model"],
                },
                quality_score=round(random.uniform(0.82, 0.93), 3),
                retry_count=1 if i in (2, 4) else 0,  # a couple of retries for realism
            )
            db.add(vt)
            db.flush()
            video_tasks.append(vt)

            vm = Media(
                project_id=project.id, task_id=vt.id,
                type="video",
                file_url=clip_urls[i],
                duration=s["end_time"] - s["start_time"],
                metadata_json={
                    "scene_label": s["label"],
                    "scene_index": i,
                    "thumbnail_url": thumb_urls[i],
                    "camera_direction": s["camera_direction"],
                    "model": s["video_model"],
                },
                sort_order=i,
            )
            db.add(vm)
            db.flush()
            video_media_rows.append(vm)

        db.commit()

        for i, (vt, vm) in enumerate(zip(video_tasks, video_media_rows)):
            ts = t0 + timedelta(seconds=100 + i * 40)
            set_timestamps(db, "tasks", vt.id, ts)
            set_timestamps(db, "media", vm.id, ts + timedelta(seconds=35))

        # ── Phase 3 : compose task + final video ────────────────────
        compose_task = Task(
            project_id=project.id,
            type="compose",
            model_name="ffmpeg",
            status="completed",
            params={
                "video_paths": clip_urls,
                "audio_path": audio_url,
            },
            result={
                "file_url": final_video_url,
                "composed": True,
                "segments": len(clip_urls),
                "duration": 258.7,
            },
            quality_score=None,
            retry_count=0,
        )
        db.add(compose_task)
        db.flush()
        set_timestamps(db, "tasks", compose_task.id, t0 + timedelta(seconds=420))

        # Two rows so every view picks it up (Studio expects video; Editor/Create expect final_video)
        final_metadata = {
            "composed": True,
            "segments": len(clip_urls),
            "thumbnail_url": thumb_urls[1],  # close-up of EIKO is a nice cover
            "loudness_lufs": -14.0,
            "resolution": "1280x544",
        }
        m_final_primary = Media(
            project_id=project.id, task_id=compose_task.id,
            type="final_video",
            file_url=final_video_url,
            duration=258.7,
            metadata_json=final_metadata,
            sort_order=0,
        )
        m_final_alias = Media(
            project_id=project.id, task_id=compose_task.id,
            type="video",
            file_url=final_video_url,
            duration=258.7,
            metadata_json={**final_metadata, "is_final": True},
            sort_order=99,
        )
        db.add_all([m_final_primary, m_final_alias])
        db.flush()
        db.commit()
        set_timestamps(db, "media", m_final_primary.id, t0 + timedelta(seconds=430))
        set_timestamps(db, "media", m_final_alias.id, t0 + timedelta(seconds=430))

        # ── Canvas (VueFlow graph) ──────────────────────────────────
        zone_nodes = [
            {"id": "zone-material", "type": "zone", "position": {"x": 18, "y": 28},
             "zIndex": -1, "draggable": False, "selectable": False,
             "style": {"width": "324px", "height": "568px"},
             "data": {"label": "素材库", "sublabel": "音乐 / 角色", "color": "#8d5cff"}},
            {"id": "zone-scene", "type": "zone", "position": {"x": 352, "y": 104},
             "zIndex": -1, "draggable": False, "selectable": False,
             "style": {"width": "250px", "height": "416px"},
             "data": {"label": "场景", "sublabel": "场景设定", "color": "#22d3ee"}},
            {"id": "zone-mv", "type": "zone", "position": {"x": 646, "y": 18},
             "zIndex": -1, "draggable": False, "selectable": False,
             "style": {"width": "860px", "height": "688px"},
             "data": {"label": "MV 制作", "sublabel": "镜头序列", "color": "#f3b2ff"}},
        ]
        song_node = {
            "id": "song1", "type": "song", "position": {"x": 60, "y": 70},
            "data": {
                "title": args.title,
                "mood": "awakening",
                "bpm": MUSIC_PLAN["bpm"],
                "duration": 258.7,
                "genre": "cinematic electronic",
                "audioUrl": audio_url,
                "lyrics": MUSIC_PLAN["lyrics_theme"],
            },
        }
        char_nodes = [
            {"id": "char_eiko", "type": "char", "position": {"x": 60, "y": 280},
             "data": {"name": "EIKO", "description": CHARACTER_BANK["EIKO"]["description"],
                      "loraId": "eiko_character_v1", "gender": "female"}},
            {"id": "char_card", "type": "char", "position": {"x": 60, "y": 460},
             "data": {"name": "扑克人群像", "description": CHARACTER_BANK["扑克人群像"]["description"],
                      "loraId": "card_suit_worker_v1", "gender": "neutral"}},
        ]
        scene_nodes = [
            {"id": "scene_office", "type": "scene", "position": {"x": 380, "y": 140},
             "data": {"name": "同化办公室", "style": "cinematic dystopian",
                      "location": "地下企业塔", "lighting": "冷白日光灯"}},
            {"id": "scene_factory", "type": "scene", "position": {"x": 380, "y": 360},
             "data": {"name": "扑克工厂", "style": "industrial surreal",
                      "location": "地下流水线", "lighting": "暖光聚光"}},
        ]
        shot_nodes = []
        shot_y_positions = [55, 165, 275, 385, 495, 605, 715]
        shot_gradients = [
            "linear-gradient(135deg,#1a1a2e,#16213e)",
            "linear-gradient(135deg,#2d1b69,#4a1942)",
            "linear-gradient(135deg,#f5af19,#f12711)",
            "linear-gradient(135deg,#0f3460,#0a2540)",
            "linear-gradient(135deg,#8b0000,#4a0000)",
            "linear-gradient(135deg,#314755,#26a0da)",
            "linear-gradient(135deg,#200122,#6f0000)",
        ]
        for i, s in enumerate(SCENES):
            shot_nodes.append({
                "id": f"s{i+1}",
                "type": "shot",
                "position": {"x": 680 + (i % 2) * 340, "y": shot_y_positions[i]},
                "data": {
                    "index": i + 1,
                    "status": "done",
                    "duration": s["end_time"] - s["start_time"],
                    "model": s["video_model"],
                    "timeAnchor": s["start_time"],
                    "gradient": shot_gradients[i],
                    "segment": s["label"],
                    "prompt": s["video_prompt"],
                    "videoUrl": clip_urls[i],
                    "thumbnailUrl": thumb_urls[i],
                },
            })

        all_nodes = zone_nodes + [song_node] + char_nodes + scene_nodes + shot_nodes

        # Edges
        EM = {"stroke": "#8d5cff", "strokeWidth": 1.5, "strokeDasharray": "5,4"}
        EC = {"stroke": "#5c9fff", "strokeWidth": 1.5, "strokeDasharray": "5,4"}
        ES = {"stroke": "#22d3ee", "strokeWidth": 1.5, "strokeDasharray": "5,4"}
        EQ = {"stroke": "rgba(255,255,255,.28)", "strokeWidth": 1.5}
        edges = []
        for i in range(len(SCENES)):
            edges.append({"id": f"em-s{i+1}", "source": "song1", "target": f"s{i+1}",
                          "type": "smoothstep", "animated": True, "style": EM,
                          "data": {"edgeType": "music-ref"}})
        # character refs
        char_shot_map = {"char_eiko": ["s2", "s6", "s7"], "char_card": ["s1", "s3"]}
        for src_c, tgts in char_shot_map.items():
            for tgt in tgts:
                edges.append({"id": f"ec-{src_c}-{tgt}", "source": src_c, "target": tgt,
                              "type": "smoothstep", "animated": False, "style": EC,
                              "data": {"edgeType": "char-ref"}})
        # scene refs
        scene_shot_map = {"scene_office": ["s1", "s2", "s5"], "scene_factory": ["s3", "s4"]}
        for src_s, tgts in scene_shot_map.items():
            for tgt in tgts:
                edges.append({"id": f"es-{src_s}-{tgt}", "source": src_s, "target": tgt,
                              "type": "smoothstep", "animated": False, "style": ES,
                              "data": {"edgeType": "scene-ref"}})
        # sequence
        for i in range(len(SCENES) - 1):
            edges.append({"id": f"eq-s{i+1}-s{i+2}", "source": f"s{i+1}", "target": f"s{i+2}",
                          "type": "smoothstep", "animated": False, "style": EQ,
                          "data": {"edgeType": "sequence"}})

        canvas = Canvas(
            project_id=project.id,
            nodes=all_nodes,
            edges=edges,
            viewport={"x": -80, "y": -20, "zoom": 0.7},
        )
        db.add(canvas)
        db.commit()
        db.refresh(canvas)
        set_timestamps(db, "canvases", canvas.id, t0 + timedelta(seconds=10))

        # CanvasShot rows
        for i, (vt, vm) in enumerate(zip(video_tasks, video_media_rows)):
            cs = CanvasShot(
                project_id=project.id,
                canvas_id=canvas.id,
                node_id=f"s{i+1}",
                prompt=SCENES[i]["video_prompt"],
                model_name=SCENES[i]["video_model"],
                duration=SCENES[i]["end_time"] - SCENES[i]["start_time"],
                time_anchor=SCENES[i]["start_time"],
                sort_order=i,
                status="done",
                canvas_context={
                    "music": "song1",
                    "characters": [c for c in ("char_eiko", "char_card")
                                   if (c == "char_eiko" and "EIKO" in SCENES[i]["characters"])
                                   or (c == "char_card" and "扑克人群像" in SCENES[i]["characters"])],
                    "scene": "scene_office" if i in (0, 1, 4) else "scene_factory" if i in (2, 3) else "scene_office",
                },
                task_id=vt.id,
                media_id=vm.id,
            )
            db.add(cs)
            db.flush()
            set_timestamps(db, "canvas_shots", cs.id, t0 + timedelta(seconds=100 + i * 40))

        db.commit()

        print("\n─────────────────────────────────────────────")
        print(f"  ✓ Project #{project.id}  —  {args.title}")
        print(f"  ✓ User: demo / demo123  (id={user_id})")
        print(f"  ✓ Scenes: {len(SCENES)}")
        print(f"  ✓ Tasks: {len(image_tasks)} image + 1 music + {len(video_tasks)} video + 1 compose")
        print(f"  ✓ Final video: {final_video_url}")
        print(f"  ✓ Canvas nodes: {len(all_nodes)}   edges: {len(edges)}")
        print("─────────────────────────────────────────────")
        print("\nOpen:")
        print(f"  http://localhost:5173/login    (demo / demo123)")
        print(f"  http://localhost:5173/projects")
        print(f"  http://localhost:5173/studio/{project.id}")
        print(f"  http://localhost:5173/canvas/{project.id}")
        print("")


if __name__ == "__main__":
    main()
