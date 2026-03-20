"""ComposeService — Merges generated video clips and audio into final MV.

Handles:
1. Video clip concatenation with transitions
2. Audio-video synchronization using beat map
3. Final muxing (video + audio → MP4)
"""

import subprocess
import tempfile
from pathlib import Path


class ComposeService:

    def concat_videos(self, video_paths: list[str], output_path: str) -> str:
        """Concatenate video clips into a single video.

        Handles both local paths and HTTP(S) URLs (e.g. MinIO presigned URLs).
        For HTTP inputs, clips are downloaded to a temp dir first so that the
        concat demuxer can copy streams without re-encoding.
        """
        import shutil, urllib.request

        resolved: list[str] = []
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            for i, p in enumerate(video_paths):
                if p.startswith("http://") or p.startswith("https://"):
                    dest = str(tmp_dir / f"clip_{i:04d}.mp4")
                    urllib.request.urlretrieve(p, dest)
                    resolved.append(dest)
                else:
                    resolved.append(p)

            list_file = tmp_dir / "concat.txt"
            list_file.write_text("\n".join(f"file '{p}'" for p in resolved))
            subprocess.run(
                [
                    "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                    "-i", str(list_file), "-c", "copy", output_path,
                ],
                check=True,
                capture_output=True,
            )
        finally:
            shutil.rmtree(tmp_dir, ignore_errors=True)
        return output_path

    def merge_audio_video(
        self, video_path: str, audio_path: str, output_path: str,
        normalize_lufs: float | None = -14.0,
    ) -> str:
        """Merge audio track with video, trimming to the shorter duration.

        Accepts local paths or HTTP(S) URLs for both inputs.
        Normalizes audio to target LUFS (EBU R128) by default — set
        normalize_lufs=None to skip normalization.
        """
        audio_filter = (
            f"loudnorm=I={normalize_lufs}:TP=-1.5:LRA=11"
            if normalize_lufs is not None
            else "anull"
        )
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-allowed_extensions", "ALL",
                "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy",
                "-af", audio_filter, "-c:a", "aac", "-b:a", "192k",
                "-shortest",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return output_path

    def normalize_loudness(
        self, audio_path: str, output_path: str, target_lufs: float = -14.0
    ) -> str:
        """Normalize audio loudness to target LUFS using FFmpeg loudnorm (EBU R128).

        -14 LUFS is the target for most streaming platforms (Spotify, YouTube, Apple Music).
        -1.5 dBTP true-peak headroom prevents clipping after encoding.
        """
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", audio_path,
                "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
                "-c:a", "aac", "-b:a", "192k",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return output_path

    def add_subtitles(self, video_path: str, srt_path: str, output_path: str) -> str:
        """Burn subtitles into video.

        The SRT path must be a local file. Colons and backslashes in path are
        escaped for the FFmpeg subtitles filter on all platforms.
        """
        # FFmpeg subtitles filter requires forward slashes and escaped colons
        safe_srt = srt_path.replace("\\", "/").replace(":", "\\:")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", (
                    f"subtitles={safe_srt}:"
                    "force_style='FontName=Arial,FontSize=18,"
                    "PrimaryColour=&H00FFFFFF,OutlineColour=&H00000000,Outline=1'"
                ),
                "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                "-c:a", "copy",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return output_path

    def add_watermark(self, video_path: str, text: str, output_path: str) -> str:
        """Add text watermark to bottom-right corner."""
        # Escape characters special to the FFmpeg drawtext filter parser
        safe_text = text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"drawtext=text='{safe_text}':fontcolor=white@0.5:fontsize=14:x=w-tw-10:y=h-th-10",
                "-c:a", "copy",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return output_path

    def export_for_platform(
        self, video_path: str, platform: str, output_path: str
    ) -> str:
        """Re-encode video for specific platform requirements.

        Accepts HTTP(S) URLs for video_path (e.g. MinIO stored final video).
        """
        presets = {
            "douyin": {"width": 1080, "height": 1920, "bitrate": "4M"},
            "bilibili": {"width": 1920, "height": 1080, "bitrate": "6M"},
            "youtube": {"width": 1920, "height": 1080, "bitrate": "8M"},
            "xiaohongshu": {"width": 1080, "height": 1440, "bitrate": "4M"},
            "instagram": {"width": 1080, "height": 1920, "bitrate": "3500k"},
        }
        preset = presets.get(platform, presets["bilibili"])
        w, h = preset["width"], preset["height"]
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-allowed_extensions", "ALL",
                "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
                "-i", video_path,
                "-vf", (
                    f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                    f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
                ),
                "-c:v", "libx264", "-preset", "fast", "-b:v", preset["bitrate"],
                "-c:a", "aac", "-b:a", "128k",
                "-movflags", "+faststart",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return output_path
