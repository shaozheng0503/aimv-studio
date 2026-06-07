"""ComposeService — Merges generated video clips and audio into final MV.

Handles:
1. Video clip concatenation with transitions
2. Audio-video synchronization using beat map
3. Final muxing (video + audio → MP4)
"""

import subprocess
import tempfile
from pathlib import Path


def _run_ffmpeg(cmd: list[str]) -> None:
    """Run an ffmpeg command; raise RuntimeError with stderr on failure."""
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except subprocess.CalledProcessError as e:
        stderr = e.stderr.decode(errors="replace").strip() if e.stderr else ""
        raise RuntimeError(
            f"ffmpeg failed (exit {e.returncode}): {stderr}"
        ) from e


class ComposeService:

    @staticmethod
    def _auto_target(sample_path: str) -> tuple[int, int]:
        """Pick a canonical target resolution matching the sample clip's orientation.

        Avoids letterboxing vertical (9:16) MVs into a landscape frame (which then
        gets padded a second time on platform export). Falls back to 1080p landscape.
        """
        if not sample_path:
            return 1920, 1080
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=width,height", "-of", "csv=p=0:s=x", sample_path],
                check=True, capture_output=True, text=True,
            ).stdout.strip()
            w, h = (int(x) for x in out.split("x")[:2])
        except Exception:
            return 1920, 1080
        if h > w:
            return 1080, 1920   # portrait
        if w == h:
            return 1080, 1080   # square
        return 1920, 1080       # landscape

    def concat_videos(
        self,
        video_paths: list[str],
        output_path: str,
        target_width: int | None = None,
        target_height: int | None = None,
    ) -> str:
        """Concatenate video clips into a single video.

        Handles both local paths and HTTP(S) URLs (e.g. MinIO presigned URLs).
        Normalises all clips to H264/AAC at target_width×target_height before
        concat — this prevents codec/resolution mismatch failures when clips
        come from different model providers (Veo, Grok, Seedance, Wan2.2).
        """
        import shutil
        import httpx

        resolved: list[str] = []
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            # Step 1: Download HTTP clips
            for i, p in enumerate(video_paths):
                if p.startswith("http://") or p.startswith("https://"):
                    dest = str(tmp_dir / f"raw_{i:04d}.mp4")
                    with httpx.stream("GET", p, timeout=120, follow_redirects=True) as r:
                        r.raise_for_status()
                        with open(dest, "wb") as f:
                            for chunk in r.iter_bytes(chunk_size=1 << 20):
                                f.write(chunk)
                    resolved.append(dest)
                else:
                    resolved.append(p)

            # Choose the target canvas. When not explicitly set, match the source
            # clips' orientation so vertical MVs aren't double-letterboxed.
            if target_width is None or target_height is None:
                target_width, target_height = self._auto_target(resolved[0] if resolved else "")

            # Step 2: Normalise each clip to target resolution + H264.
            # Video clips from cloud APIs (Veo, Grok, Seedance) may differ in
            # resolution, codec, or pixel format.  We re-encode to H264 with
            # scale+pad so the concat demuxer sees identical stream parameters.
            # Audio is stripped here — the music track is merged in merge_audio_video.
            normalised: list[str] = []
            scale_filter = (
                f"scale={target_width}:{target_height}:"
                f"force_original_aspect_ratio=decrease,"
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:color=black,"
                f"setsar=1,fps=fps=24"
            )
            for i, src in enumerate(resolved):
                norm_path = str(tmp_dir / f"norm_{i:04d}.mp4")
                _run_ffmpeg([
                    "ffmpeg", "-y",
                    "-i", src,
                    "-vf", scale_filter,
                    "-c:v", "libx264", "-preset", "fast", "-crf", "18",
                    "-an",          # strip audio — music is added in compose step
                    norm_path,
                ])
                normalised.append(norm_path)

            # Step 3: Concat normalised clips (same codec/resolution → copy is safe)
            list_file = tmp_dir / "concat.txt"
            list_file.write_text("\n".join(f"file '{p}'" for p in normalised))
            _run_ffmpeg([
                "ffmpeg", "-y", "-f", "concat", "-safe", "0",
                "-i", str(list_file), "-c", "copy", output_path,
            ])
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
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", video_path,
            "-i", audio_path,
            # Explicit mapping: video from input 0, music from input 1. Don't rely
            # on ffmpeg's default stream selection.
            "-map", "0:v:0", "-map", "1:a:0",
            "-c:v", "copy",
            "-af", audio_filter, "-c:a", "aac", "-b:a", "192k",
            "-shortest",
            output_path,
        ])
        return output_path

    def normalize_loudness(
        self, audio_path: str, output_path: str, target_lufs: float = -14.0
    ) -> str:
        """Normalize audio loudness to target LUFS using FFmpeg loudnorm (EBU R128).

        -14 LUFS is the target for most streaming platforms (Spotify, YouTube, Apple Music).
        -1.5 dBTP true-peak headroom prevents clipping after encoding.
        """
        _run_ffmpeg([
            "ffmpeg", "-y", "-i", audio_path,
            "-af", f"loudnorm=I={target_lufs}:TP=-1.5:LRA=11",
            "-c:a", "aac", "-b:a", "192k",
            output_path,
        ])
        return output_path

    def add_subtitles(self, video_path: str, srt_path: str, output_path: str) -> str:
        """Burn subtitles into video.

        The SRT path must be a local file. Colons and backslashes in path are
        escaped for the FFmpeg subtitles filter on all platforms.
        """
        # FFmpeg subtitles filter requires forward slashes and escaped colons
        safe_srt = srt_path.replace("\\", "/").replace(":", "\\:")
        _run_ffmpeg([
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
        ])
        return output_path

    def add_watermark(self, video_path: str, text: str, output_path: str) -> str:
        """Add text watermark to bottom-right corner."""
        # Escape characters special to the FFmpeg drawtext filter parser
        safe_text = text.replace("\\", "\\\\").replace("'", "\\'").replace(":", "\\:")
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", f"drawtext=text='{safe_text}':fontcolor=white@0.5:fontsize=14:x=w-tw-10:y=h-th-10",
            "-c:a", "copy",
            output_path,
        ])
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
        _run_ffmpeg([
            "ffmpeg", "-y",
            "-i", video_path,
            "-vf", (
                f"scale={w}:{h}:force_original_aspect_ratio=decrease,"
                f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2:color=black"
            ),
            "-c:v", "libx264", "-preset", "fast", "-b:v", preset["bitrate"],
            "-c:a", "aac", "-b:a", "128k",
            "-movflags", "+faststart",
            output_path,
        ])
        return output_path
