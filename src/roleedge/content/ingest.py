"""Turn shared media into model input: text plus images (video becomes sampled frames), or the video itself for a
model that watches it whole (Muse Spark reads ``input_video``), and stills taken at the moments that matter."""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ContentItem:
    """Something shared into a chat, ready for the model: a text description and any images."""

    text: str
    images: list[Path] = field(default_factory=list)

    def message_parts(self) -> list[dict[str, Any]]:
        return [{"type": "text", "text": self.text}] + [image_part(p) for p in self.images]


def image_part(path: Path) -> dict[str, Any]:
    mime = "image/png" if path.suffix == ".png" else "image/jpeg"
    encoded = base64.b64encode(path.read_bytes()).decode()
    return {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{encoded}"}}


VIDEO_PART_MAX_BYTES = 12_000_000  # above this (or if not H.264) the video is re-encoded smaller before it is sent
VIDEO_PART_MAX_SECONDS = 180  # the watcher sees at most the first three minutes


def _probe(video: Path) -> dict[str, Any]:
    out = subprocess.run(["ffprobe", "-v", "error", "-print_format", "json", "-show_format", "-show_streams", str(video)],
                         capture_output=True, text=True, timeout=30, check=False).stdout
    try:
        return json.loads(out or "{}")
    except ValueError:
        return {}


def video_part(video: Path) -> dict[str, Any]:
    """The whole video as one message part (a data URL). An H.264 MP4 under 12 MB goes as it is; anything else is
    re-encoded to 540p H.264 at a low bitrate (a reel stays readable: faces, movements, on-screen text)."""
    meta = _probe(video)
    codec = next((s.get("codec_name") for s in meta.get("streams", []) if s.get("codec_type") == "video"), "")
    duration = float((meta.get("format") or {}).get("duration") or 0)
    if codec == "h264" and video.stat().st_size <= VIDEO_PART_MAX_BYTES and duration <= VIDEO_PART_MAX_SECONDS:
        data = video.read_bytes()
    else:
        with tempfile.TemporaryDirectory() as tmp:
            small = Path(tmp) / "small.mp4"
            subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-t", str(VIDEO_PART_MAX_SECONDS),
                            "-vf", "scale=-2:'min(540,ih)'", "-c:v", "libx264", "-preset", "veryfast", "-crf", "30",
                            "-c:a", "aac", "-b:a", "64k", "-movflags", "+faststart", str(small)], check=True, timeout=300)
            data = small.read_bytes()
    return {"type": "video_url", "video_url": {"url": "data:video/mp4;base64," + base64.b64encode(data).decode()}}


def frames_at(video: Path, times: list[float], frames_dir: Path, width: int = 512) -> list[Path]:
    """One still at each time (seconds), named t01.jpg, t02.jpg... in that order: the moments a timeline points at."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("t*.jpg"):
        old.unlink()
    made = []
    for k, t in enumerate(times, start=1):
        out = frames_dir / f"t{k:02d}.jpg"
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-ss", f"{max(0.0, t):.2f}", "-i", str(video), "-frames:v", "1",
                        "-vf", f"scale={width}:-2", "-q:v", "4", str(out)], check=False, timeout=60)
        if out.exists():
            made.append(out)
    return made


def spread_frames(video: Path, frames_dir: Path, count: int = 8, width: int = 512) -> list[Path]:
    """``count`` frames spread evenly over the whole video (a 60 s reel gets one every 7.5 s), wide enough for the
    model to read on-screen text. The audio track goes to speech-to-text separately."""
    probe = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(video)],
                           capture_output=True, text=True, timeout=30, check=False)
    try:
        duration = max(1.0, float(probe.stdout.strip()))
    except ValueError:
        duration = 30.0
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("*.jpg"):
        old.unlink()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps={count}/{duration:.2f},scale={width}:-2",
                    "-frames:v", str(count), "-q:v", "4", str(frames_dir / "f%02d.jpg")], check=True, timeout=120)
    return sorted(frames_dir.glob("*.jpg"))


def video_frames(video: Path, frames_dir: Path, every_s: float = 3.0, max_frames: int = 6) -> list[Path]:
    """Sample frames a vision model can 'watch'. The audio track goes to speech-to-text separately."""
    frames_dir.mkdir(parents=True, exist_ok=True)
    for old in frames_dir.glob("*.jpg"):
        old.unlink()
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(video), "-vf", f"fps=1/{every_s},scale=360:-1",
                    "-frames:v", str(max_frames), str(frames_dir / "f%02d.jpg")], check=True)
    return sorted(frames_dir.glob("*.jpg"))
