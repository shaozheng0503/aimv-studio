"""ShotRouter — Routes each storyboard segment to the correct video generation pipeline.

Two tracks:
- "sing" segments → lip-sync pipeline (character singing on screen)
- "story" segments → cinematic pipeline (narrative scenes)

Also handles frame-chaining: extracting last frame of shot N as first frame of shot N+1.
"""

import subprocess
import tempfile
from pathlib import Path
from dataclasses import dataclass


@dataclass
class ShotPlan:
    segment_id: int
    label: str          # "sing" or "story"
    prompt: str
    video_model: str
    first_frame: str    # URL or path of first frame reference image
    duration: float
    camera_direction: dict
    character_name: str


class ShotRouter:

    def route_shot(
        self,
        segment: dict,
        visual_style: str = "",
        previous_last_frame: str = "",
    ) -> ShotPlan:
        """Determine which pipeline and model to use for a storyboard segment."""

        label = segment.get("label", "story")
        prompt = segment.get("video_prompt", segment.get("description", ""))
        character_name = (segment.get("characters") or [""])[0]
        duration = segment.get("end_time", 0) - segment.get("start_time", 0)
        camera = segment.get("camera_direction", {})

        if label == "sing":
            # Singing segments → use Seedance (dance/performance) or Wan2.2 (lip-sync)
            model = self._route_sing(visual_style)
        else:
            # Story segments → route by visual style
            model = self._route_story(visual_style)

        return ShotPlan(
            segment_id=segment.get("segment_id", 0),
            label=label,
            prompt=prompt,
            video_model=model,
            first_frame=previous_last_frame,
            duration=max(duration, 3.0),  # minimum 3 seconds
            camera_direction=camera,
            character_name=character_name,
        )

    def _route_sing(self, style: str) -> str:
        """Singing segments need models good at human performance."""
        style_map = {
            "韩娱": "seedance",       # Dance + performance
            "国风": "veo",            # Graceful movement
            "复古迪斯科": "seedance", # Dance
        }
        return style_map.get(style, "seedance")

    def _route_story(self, style: str) -> str:
        """Story segments need cinematic quality."""
        style_map = {
            "韩娱": "veo",
            "国风": "veo",
            "独立电影": "veo",
            "赛博朋克": "grok",
            "幻想童话": "grok",
            "复古迪斯科": "grok",
            "都市甜酷": "grok",
        }
        return style_map.get(style, "veo")

    @staticmethod
    def extract_last_frame(video_path: str) -> str:
        """Extract the last frame of a video for frame-chaining.

        Returns path to the extracted frame image.
        """
        import os
        fd, output = tempfile.mkstemp(suffix=".jpg")
        os.close(fd)
        try:
            subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-allowed_extensions", "ALL",
                    "-protocol_whitelist", "file,http,https,tcp,tls,crypto",
                    "-sseof", "-0.1",
                    "-i", video_path,
                    "-update", "1",
                    "-q:v", "2",
                    output,
                ],
                check=True,
                capture_output=True,
            )
            return output
        except subprocess.CalledProcessError:
            try:
                os.unlink(output)
            except OSError:
                pass
            return ""

    def plan_all_shots(
        self,
        storyboard: list[dict],
        visual_style: str = "",
    ) -> list[ShotPlan]:
        """Plan all shots with frame-chaining.

        The first shot has no previous frame.
        Each subsequent shot uses the last frame of the previous shot.
        """
        plans = []
        prev_frame = ""

        for segment in storyboard:
            plan = self.route_shot(segment, visual_style, prev_frame)
            plans.append(plan)
            # first_frame for each plan is set here to "" — the actual frame URLs
            # are resolved during execution in run_video_phase, which maintains
            # its own prev_last_frame after each shot completes.

        return plans
