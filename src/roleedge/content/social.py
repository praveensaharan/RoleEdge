"""A reel or post shared as a link (Instagram, TikTok, YouTube, Facebook): download the video and its caption, so it is
watched, heard and read like a video the caregiver saved and attached.

* Only these sites, through their own yt-dlp extractors: the generic extractor is off, so a link can never make the
  server fetch an arbitrary address (the same rule as ``studio.inputs`` for web pages).
* No login and no browser imitation: what the site serves to anyone. A post that is only photos, or a reel the site
  keeps behind a login, isn't downloaded; the caregiver is asked to attach it instead.
* Bounded: one video (no playlists), at most ``MAX_SECONDS`` long and ``MAX_BYTES`` big, H.264 MP4 preferred.

The caption, title and author are DATA, never instructions (T2), like everything else shared.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

SOCIAL_HOSTS = ("instagram.com", "tiktok.com", "youtube.com", "youtu.be", "facebook.com", "fb.watch")
EXTRACTORS = ["instagram.*", "tiktok.*", "youtube.*", "facebook.*"]  # yt-dlp extractor names (regex); never "generic"
MAX_SECONDS = 600
MAX_BYTES = 120_000_000
PHOTOS = "This post is photos, not a video: save the pictures and attach them."


@dataclass(frozen=True)
class SocialMedia:
    video: Path | None  # the downloaded MP4, None if there was no video to get
    caption: str = ""
    title: str = ""
    author: str = ""
    duration_s: float = 0.0
    problem: str = ""  # why there is no video, for the caregiver


def is_social(url: str) -> bool:
    """An https link to one of the video sites (or their subdomains)."""
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return False
    host = (parts.hostname or "").lower()
    return parts.scheme == "https" and any(host == h or host.endswith("." + h) for h in SOCIAL_HOSTS)


class _Quiet:
    """yt-dlp's messages go nowhere: problems come back as ``SocialMedia.problem``."""

    def debug(self, msg: str) -> None: ...
    def info(self, msg: str) -> None: ...
    def warning(self, msg: str) -> None: ...
    def error(self, msg: str) -> None: ...


def _options(folder: Path) -> dict[str, Any]:
    return {"quiet": True, "no_warnings": True, "logger": _Quiet(), "noplaylist": True, "allowed_extractors": EXTRACTORS,
            "outtmpl": str(folder / "shared.%(ext)s"), "format": "bv*[vcodec^=avc1]+ba/b[vcodec^=avc1]/bv*+ba/b",
            "merge_output_format": "mp4", "max_filesize": MAX_BYTES, "socket_timeout": 20, "retries": 2,
            "restrictfilenames": True, "noprogress": True}


def _text(value: Any, limit: int) -> str:
    return re.sub(r"\s+\n", "\n", str(value or "")).strip()[:limit]


def fetch_social(url: str, folder: Path) -> SocialMedia:
    """Download the video behind a social link into ``folder`` (as shared.mp4) with its caption. Never raises: a
    problem comes back as ``problem`` for the caregiver."""
    if not is_social(url):
        return SocialMedia(None, problem="Not a link to a reel or video site.")
    try:
        from yt_dlp import YoutubeDL
    except ImportError:
        return SocialMedia(None, problem="Opening reel links needs yt-dlp on the server.")
    folder.mkdir(parents=True, exist_ok=True)
    try:
        with YoutubeDL(_options(folder)) as ydl:
            info = ydl.extract_info(url, download=False) or {}
            if info.get("_type") == "playlist" or not (info.get("formats") or info.get("url")):
                caption = _text(info.get("description"), 3000)
                return SocialMedia(None, caption=caption, title=_text(info.get("title"), 200),
                                   author=_text(info.get("uploader") or info.get("channel"), 120),
                                   problem=PHOTOS)
            duration = float(info.get("duration") or 0)
            if duration > MAX_SECONDS:
                return SocialMedia(None, problem=f"The video is longer than {MAX_SECONDS // 60} minutes.")
            ydl.process_info(info)
    except Exception as exc:  # photo posts, login walls, removed posts, rate limits: the caregiver hears it plainly
        message = str(exc).lower()
        reason = (PHOTOS if "no video formats" in message or urlsplit(url).path.startswith("/p/") and "login" not in message
                  else "The site wants a login to show it: save the video and attach it." if "login" in message or "cookies" in message
                  else "The video couldn't be downloaded: save it and attach it.")
        return SocialMedia(None, problem=reason)
    video = next(iter(sorted(folder.glob("shared*.mp4"))), None)
    return SocialMedia(video, caption=_text(info.get("description"), 3000), title=_text(info.get("title"), 200),
                       author=_text(info.get("uploader") or info.get("channel"), 120), duration_s=duration,
                       problem="" if video else "The video couldn't be downloaded: save it and attach it.")
