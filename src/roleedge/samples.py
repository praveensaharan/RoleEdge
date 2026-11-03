"""Generate the synthetic media samples in data/samples/ (all fictional):

* reel_pension.mp4 - a vertical 'reel' with on-screen text slides
* bill_photo.png   - a photo-like render of data/samples/source/bill.html

Text samples (transcripts, the school notice) are checked-in files next to them.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

from .config import SAMPLES_DIR
from .render.browser import HtmlRenderer

FONT = "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
REEL_SLIDES = [  # (background, big text, small text), 3 seconds each
    ("#e60000", "PENSIONERS ALERT", "Life Certificate due!"),
    ("#25282b", "1 - 30 NOVEMBER", "80+ years: from 1 October"),
    ("#0b6e4f", "3 EASY WAYS", "Bank  |  Face app  |  Doorstep"),
    ("#e60000", "MISS IT?", "Pension may stop in December"),
]


def make_reel(out: Path = SAMPLES_DIR / "reel_pension.mp4") -> Path:
    parts = []
    for i, (bg, big, small) in enumerate(REEL_SLIDES):
        part = out.parent / f".slide{i}.mp4"
        text = (f"drawtext=fontfile={FONT}:text='{big}':fontcolor=white:fontsize=64:x=(w-text_w)/2:y=h/2-120,"
                f"drawtext=fontfile={FONT}:text='{small}':fontcolor=white:fontsize=38:x=(w-text_w)/2:y=h/2+10,"
                f"drawtext=fontfile={FONT}:text='@pension.updates.daily':fontcolor=white@0.7:fontsize=26:x=40:y=h-90")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "lavfi", "-i", f"color=c={bg}:s=720x1280:d=3:r=25",
                        "-f", "lavfi", "-i", "sine=frequency=330:duration=3", "-vf", text, "-c:v", "libx264",
                        "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(part)], check=True)
        parts.append(part)
    listing = out.parent / ".slides.txt"
    listing.write_text("".join(f"file '{p.name}'\n" for p in parts))
    try:
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(listing),
                        "-c", "copy", str(out)], check=True)
    finally:
        for p in [*parts, listing]:
            p.unlink(missing_ok=True)
    return out


def make_bill(out: Path = SAMPLES_DIR / "bill_photo.png") -> Path:
    with HtmlRenderer() as renderer:
        renderer.screenshot((SAMPLES_DIR / "source" / "bill.html").read_text(encoding="utf-8"), out, 840, 700)
    return out


def ensure_samples(force: bool = False) -> list[Path]:
    """Create media samples that are missing (or all of them with ``force``)."""
    made = []
    for path, maker in ((SAMPLES_DIR / "reel_pension.mp4", make_reel), (SAMPLES_DIR / "bill_photo.png", make_bill)):
        if force or not path.exists():
            made.append(maker(path))
    return made
