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
        """Concatenate video clips into a single video using FFmpeg concat demuxer."""
        list_file = Path(tempfile.mktemp(suffix=".txt"))
        list_file.write_text(
            "\n".join(f"file '{p}'" for p in video_paths)
        )
        subprocess.run(
            [
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file), "-c", "copy", output_path,
            ],
            check=True,
            capture_output=True,
        )
        list_file.unlink(missing_ok=True)
        return output_path

    def merge_audio_video(self, video_path: str, audio_path: str, output_path: str) -> str:
        """Merge audio track with video, trimming to the shorter duration."""
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-i", audio_path,
                "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
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
        """Burn subtitles into video."""
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"subtitles={srt_path}:force_style='FontSize=18,PrimaryColour=&HFFFFFF&'",
                "-c:a", "copy",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return output_path

    def add_watermark(self, video_path: str, text: str, output_path: str) -> str:
        """Add text watermark to bottom-right corner."""
        subprocess.run(
            [
                "ffmpeg", "-y",
                "-i", video_path,
                "-vf", f"drawtext=text='{text}':fontcolor=white@0.5:fontsize=14:x=w-tw-10:y=h-th-10",
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
        """Re-encode video for specific platform requirements."""
        presets = {
            "douyin": {"width": 1080, "height": 1920, "bitrate": "4M"},   # 9:16 vertical
            "bilibili": {"width": 1920, "height": 1080, "bitrate": "6M"},  # 16:9
            "youtube": {"width": 1920, "height": 1080, "bitrate": "8M"},   # 16:9 high quality
            "xiaohongshu": {"width": 1080, "height": 1440, "bitrate": "4M"},  # 3:4
        }
        preset = presets.get(platform, presets["bilibili"])
        subprocess.run(
            [
                "ffmpeg", "-y", "-i", video_path,
                "-vf", f"scale={preset['width']}:{preset['height']}:force_original_aspect_ratio=decrease,pad={preset['width']}:{preset['height']}:(ow-iw)/2:(oh-ih)/2",
                "-c:v", "libx264", "-b:v", preset["bitrate"],
                "-c:a", "aac", "-b:a", "128k",
                output_path,
            ],
            check=True,
            capture_output=True,
        )
        return output_path
