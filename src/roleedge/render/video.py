"""The explainer video: one frame per storyboard scene, slow zoom, slide transitions (ffmpeg).

Silent for now: narration needs a text-to-speech provider (see docs/FINDINGS.md).
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from ..models import Scene
from .browser import HtmlRenderer
from .theme import COLORS, TEMPLATES

WIDTH, HEIGHT, FPS = 720, 1280, 25
FADE_S = 0.5
MAX_SCENES = 6
MIN_SCENE_S, MAX_SCENE_S = 3, 6

NORMAL_PALETTE = [(COLORS["ink"], "#fff"), (COLORS["canvas_soft"], COLORS["ink"]), ("#fff", COLORS["ink"])]
WARNING_PALETTE = [(COLORS["danger"], "#fff"), (COLORS["ink"], "#fff")]


def scene_html(scene: Scene, index: int, total: int, warn: bool) -> str:
    palette = WARNING_PALETTE if warn else NORMAL_PALETTE
    bg, fg = palette[index % len(palette)]
    return TEMPLATES.get_template("scene.html").render(scene=scene, index=index, total=total, bg=bg, fg=fg)


def scene_seconds(scene: Scene) -> int:
    return max(MIN_SCENE_S, min(MAX_SCENE_S, int(scene.seconds)))


def video_length(seconds: list[int]) -> float:
    return round(sum(seconds) - FADE_S * (len(seconds) - 1), 1)


def render_explainer(renderer: HtmlRenderer, scenes: list[Scene], frames_dir: Path, out: Path, warn: bool) -> list[int]:
    """Render frames, then the MP4. Returns the seconds used per scene."""
    scenes = scenes[:MAX_SCENES]
    frames = [renderer.screenshot(scene_html(s, i, len(scenes), warn), frames_dir / f"scene{i}.png", WIDTH, HEIGHT)
              for i, s in enumerate(scenes)]
    seconds = [scene_seconds(s) for s in scenes]
    build_video(frames, seconds, out)
    return seconds


def build_video(frames: list[Path], seconds: list[int], out: Path) -> None:
    segments = [_zoom_segment(f, s) for f, s in zip(frames, seconds, strict=True)]
    try:
        _join_with_slides(segments, seconds, out)
    finally:
        for seg in segments:
            seg.unlink(missing_ok=True)


def _zoom_segment(frame: Path, seconds: int) -> Path:
    """A still frame with a slow 'Ken Burns' zoom (upscaled first to avoid jitter)."""
    segment = frame.with_suffix(".mp4")
    n = int(seconds * FPS)
    zoom = (f"scale={WIDTH * 2}:{HEIGHT * 2},zoompan=z='min(zoom+0.0007,1.06)':d={n}:"
            f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s={WIDTH}x{HEIGHT}:fps={FPS}")
    _ffmpeg("-i", str(frame), "-vf", zoom, "-frames:v", str(n), "-c:v", "libx264", "-pix_fmt", "yuv420p",
            "-preset", "veryfast", str(segment))
    return segment


def _join_with_slides(segments: list[Path], seconds: list[int], out: Path) -> None:
    inputs = [arg for seg in segments for arg in ("-i", str(seg))]
    chain, offset, last = [], 0.0, "[0:v]"
    for k in range(1, len(segments)):
        offset += seconds[k - 1] - FADE_S
        chain.append(f"{last}[{k}:v]xfade=transition=slideleft:duration={FADE_S}:offset={offset:.2f}[v{k}]")
        last = f"[v{k}]"
    mapping = ["-filter_complex", ";".join(chain), "-map", last] if chain else []
    _ffmpeg(*inputs, *mapping, "-c:v", "libx264", "-pix_fmt", "yuv420p", "-preset", "veryfast",
            "-movflags", "+faststart", str(out))


def _ffmpeg(*args: str) -> None:
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", *args], check=True)
