"""Build one avatar: a portrait plus mouth and blink frames, aligned by SAM 3.1 boxes and composited in code."""

from __future__ import annotations

import io
import json
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

from ..config import REPO_ROOT
from ..llm.meta_media import Box, MetaMedia

# Demo avatars are synthetic people drawn by Muse Image, kept with the web app so the judge path works offline.
AVATAR_DIR = REPO_ROOT / "web" / "app" / "avatars"
FRAME_SIZE = 640

CHARACTER_STYLE = ("stylized 3D animated character portrait, soft rounded features, large warm expressive eyes, smooth "
                   "clean shading, friendly and calm, high-quality 3D character render, head and shoulders, facing the "
                   "camera directly, plain soft light-grey background, a little space above the head")
PHOTO_STYLE = ("photorealistic head-and-shoulders portrait, plain light grey studio background, facing the camera "
               "directly, soft even daylight, sharp focus, centered, a little space above the head")
PEOPLE: dict[str, str] = {
    "kenji": "a friendly Japanese man in his early forties with short black hair and a navy crew-neck sweater, gentle "
             "smile with lips closed",
    "maya": "a friendly Chinese-American woman in her late thirties with shoulder-length dark hair and a sage-green "
            "blouse, gentle smile with lips closed",
}
STYLES = {"character": CHARACTER_STYLE, "photo": PHOTO_STYLE}
PORTRAITS: dict[str, str] = {person: f"{STYLES['character']}: {who}" for person, who in PEOPLE.items()}


def portrait_prompt(person_id: str, style: str = "character") -> str:
    return f"{STYLES[style]}: {PEOPLE[person_id]}"


KEEP = ("Keep the same character, art style, pose, framing, lighting, clothes and background exactly as they are; "
        "change nothing else.")
VARIANTS: dict[str, tuple[str, str]] = {  # frame -> (what to find with SAM, edit instruction)
    "open": ("mouth", "Edit this photo: open the mouth naturally, mid-word, as if saying 'ah', upper teeth slightly "
                      "visible. " + KEEP),
    "half": ("mouth", "Edit this photo: part the lips slightly, as if saying 'oh' softly. " + KEEP),
    "blink": ("eye", "Edit this photo: close both eyes gently, a natural blink, mouth unchanged. " + KEEP),
}


def build_avatar(media: MetaMedia, person_id: str, out_dir: Path = AVATAR_DIR, prompt: str | None = None,
                 base_image: bytes | None = None, style: str = "character", folder_name: str | None = None) -> dict:
    """Make ``out_dir/<person_id>/{base,open,half,blink}.jpg`` and ``avatar.json``. Pass ``base_image`` to animate an
    existing portrait (for example the caregiver's own photo, with their consent) instead of generating one."""
    folder = out_dir / (folder_name or person_id)
    prompt = prompt or (portrait_prompt(person_id, style) if person_id in PEOPLE else None)
    folder.mkdir(parents=True, exist_ok=True)
    steps: list[dict] = []
    started = time.time()
    if base_image is None:
        if not prompt:
            raise ValueError(f"No portrait description for '{person_id}'; pass prompt= or base_image=")
        base_image = media.generate_image(prompt)
        steps.append({"step": "Drew the portrait", "engine": "meta/muse-image-1.0", "s": round(time.time() - started, 1)})
    base = _open(base_image)
    found = {noun: _timed(steps, f"Found the {noun}", lambda n=noun: media.find(base_image, n)) for noun in ("mouth", "eye")}
    if not found["mouth"] or not found["eye"]:
        raise RuntimeError(f"SAM 3.1 did not find {'the mouth' if not found['mouth'] else 'the eyes'} in the portrait")

    frames = {"base": base}
    for frame, (noun, instruction) in VARIANTS.items():
        edited_bytes = _timed(steps, f"Made the '{frame}' frame", lambda i=instruction: media.edit_image(base_image, i),
                              engine="meta/muse-image-1.0")
        edited = _open(edited_bytes).resize(base.size)
        boxes = _timed(steps, f"Found the {noun} in the '{frame}' frame", lambda b=edited_bytes, n=noun: media.find(b, n))
        frames[frame] = _paste_region(base, edited, found[noun], boxes, base.size)

    for name, image in frames.items():
        image.resize((FRAME_SIZE, FRAME_SIZE), Image.LANCZOS).save(folder / f"{name}.jpg", quality=88)
    scale = FRAME_SIZE / base.size[0]
    meta = {"person": person_id, "frames": list(frames), "size": FRAME_SIZE,
            "mouth": _scaled(_union(found["mouth"], base.size), scale), "eyes": _scaled(_union(found["eye"], base.size), scale),
            "style": style if base_image is not None and prompt else "photo-upload", "prompt": prompt or "",
            "steps": steps,
            "note": "Drawn by Muse Image (synthetic person); frames aligned with SAM 3.1 boxes and composited in code."}
    (folder / "avatar.json").write_text(json.dumps(meta, indent=1), encoding="utf-8")
    return meta


def _timed(steps: list[dict], label: str, call, engine: str = "meta/sam-3.1"):
    started = time.time()
    result = call()
    steps.append({"step": label, "engine": engine, "s": round(time.time() - started, 1)})
    return result


def _open(data: bytes) -> Image.Image:
    return Image.open(io.BytesIO(data)).convert("RGB")


def _union(boxes: list[Box], size: tuple[int, int]) -> tuple[float, float, float, float]:
    """One box around all matches, in the coordinates of an image of ``size``."""
    sx = size[0] / (boxes[0].width or size[0])
    sy = size[1] / (boxes[0].height or size[1])
    return (min(b.x1 for b in boxes) * sx, min(b.y1 for b in boxes) * sy,
            max(b.x2 for b in boxes) * sx, max(b.y2 for b in boxes) * sy)


def _scaled(box: tuple[float, float, float, float], scale: float) -> list[int]:
    return [round(v * scale) for v in box]


def _paste_region(base: Image.Image, edited: Image.Image, base_boxes: list[Box], edited_boxes: list[Box],
                  size: tuple[int, int]) -> Image.Image:
    """Copy the region around the feature from ``edited`` onto ``base`` with a soft elliptical edge. If SAM found the
    feature in the edited frame too, shift the copy so its centre lands on the base feature's centre."""
    x1, y1, x2, y2 = _union(base_boxes, size)
    w, h = x2 - x1, y2 - y1
    pad_x, pad_y = w * 0.35, h * 0.9  # room for an open jaw
    region = (int(x1 - pad_x), int(y1 - pad_y * 0.6), int(x2 + pad_x), int(y2 + pad_y))
    dx = dy = 0.0
    if edited_boxes:
        ex1, ey1, ex2, ey2 = _union(edited_boxes, size)
        dx, dy = (ex1 + ex2) / 2 - (x1 + x2) / 2, (ey1 + ey2) / 2 - (y1 + y2) / 2
    source = (int(region[0] + dx), int(region[1] + dy), int(region[2] + dx), int(region[3] + dy))
    patch = edited.crop(source)
    mask = Image.new("L", patch.size, 0)
    inset = max(4, int(min(patch.size) * 0.12))
    ImageDraw.Draw(mask).ellipse((inset, inset, patch.size[0] - inset, patch.size[1] - inset), fill=255)
    mask = mask.filter(ImageFilter.GaussianBlur(inset * 0.8))
    out = base.copy()
    out.paste(patch, region[:2], mask)
    return out
