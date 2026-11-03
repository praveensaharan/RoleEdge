"""Meta's non-chat models: Muse Image (generate, edit), SAM 3.1 (find objects) and Muse Voice Transcribe.

Wire formats follow dev.meta.ai (checked 2026-11-01):

* images: ``POST /v1/images/generations`` and ``/v1/images/edits`` (JSON, ``images: [{image_url: data-URL}]``),
  reply ``data[0].b64_json``;
* SAM 3.1: ``POST /v1/responses`` with an image and one short noun phrase, streamed; the text holds one record
  per match: an object id, ``<|box;x1=..;y1=..;x2=..;y2=..;w=..;h=..|>`` (source pixels), then a mask token. We use
  the boxes only;
* transcription: ``POST /v1/asr/transcribe``, multipart (``request`` JSON + ``audio`` WAV, mono 16-bit 16/24 kHz),
  reply ``{transcript, audioDurationMs, turns: [{startMs, endMs, transcript}]}``.
"""

from __future__ import annotations

import base64
import json
import re
import time
from dataclasses import dataclass
from typing import Any

import httpx

from ..config import MetaConfig
from .types import ProviderError

IMAGE_MODEL = "muse-image-1.0"
SAM_MODEL = "sam-3.1"
TRANSCRIBE_MODEL = "muse-voice-transcribe-1.0"
_BOX = re.compile(r"<\|box;([^|]*)\|>")


@dataclass(frozen=True)
class Box:
    x1: float
    y1: float
    x2: float
    y2: float
    width: int  # source image size
    height: int

    @property
    def center(self) -> tuple[float, float]:
        return (self.x1 + self.x2) / 2, (self.y1 + self.y2) / 2


@dataclass(frozen=True)
class Transcript:
    text: str
    duration_s: float
    turns: list[dict[str, Any]]
    latency_s: float


class MetaMedia:
    name = "meta"

    def __init__(self, config: MetaConfig, timeout_s: float = 180.0) -> None:
        self.config = config
        self.base = config.responses_url.rsplit("/responses", 1)[0]
        self.timeout = timeout_s

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.config.api_key}"}

    def _check(self, res: httpx.Response) -> None:
        if res.status_code >= 400:
            raise ProviderError(self.name, f"{res.request.url.path}: {res.text[:300]}", res.status_code)

    # ---------------------------------------------------------------- Muse Image

    def generate_image(self, prompt: str, size: str = "1024x1024", output_format: str = "png") -> bytes:
        body = {"model": IMAGE_MODEL, "prompt": prompt, "n": 1, "size": size, "output_format": output_format}
        res = httpx.post(f"{self.base}/images/generations", json=body, headers=self._headers(), timeout=self.timeout)
        self._check(res)
        return base64.b64decode(res.json()["data"][0]["b64_json"])

    def edit_image(self, image: bytes, prompt: str, mime: str = "image/png") -> bytes:
        data_url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        body = {"model": IMAGE_MODEL, "prompt": prompt, "images": [{"image_url": data_url}], "n": 1}
        res = httpx.post(f"{self.base}/images/edits", json=body, headers=self._headers(), timeout=self.timeout)
        self._check(res)
        return base64.b64decode(res.json()["data"][0]["b64_json"])

    # ---------------------------------------------------------------- SAM 3.1

    def find(self, image: bytes, noun: str, mime: str = "image/png") -> list[Box]:
        """Boxes of every ``noun`` in the image (one short noun phrase per call, as Meta recommends)."""
        data_url = f"data:{mime};base64,{base64.b64encode(image).decode()}"
        body = {"model": SAM_MODEL, "stream": True,
                "input": [{"role": "user", "content": [{"type": "input_text", "text": noun},
                                                        {"type": "input_image", "image_url": data_url}]}]}
        text = []
        headers = {**self._headers(), "Accept": "text/event-stream"}
        with httpx.stream("POST", f"{self.base}/responses", json=body, headers=headers, timeout=self.timeout) as res:
            if res.status_code >= 400:
                res.read()
                self._check(res)
            for line in res.iter_lines():
                if not line.startswith("data:"):
                    continue
                payload = line[5:].strip()
                if payload in ("", "[DONE]"):
                    continue
                event = json.loads(payload)
                if event.get("type") == "response.output_text.delta":
                    text.append(event.get("delta", ""))
        return [_box(m.group(1)) for m in _BOX.finditer("".join(text))]

    # ---------------------------------------------------------------- Voice Transcribe

    def transcribe(self, wav: bytes, languages: list[str] | None = None, keywords: list[str] | None = None) -> Transcript:
        request: dict[str, Any] = {"mode": "PUSH_TO_TALK", "model": TRANSCRIBE_MODEL, "audioEncoding": "WAV"}
        if languages:
            request["languageBias"] = languages
        if keywords:
            request["keywords"] = keywords
        files = {"request": (None, json.dumps(request), "application/json"), "audio": ("reply.wav", wav, "audio/wav")}
        started = time.time()
        res = httpx.post(f"{self.base}/asr/transcribe", files=files,
                         headers={**self._headers(), "Accept": "application/json"}, timeout=self.timeout)
        self._check(res)
        data = res.json()
        return Transcript(text=(data.get("transcript") or "").strip(),
                          duration_s=(data.get("audioDurationMs") or 0) / 1000, turns=data.get("turns") or [],
                          latency_s=round(time.time() - started, 2))


def _box(fields: str) -> Box:
    values = dict(part.split("=", 1) for part in fields.split(";") if "=" in part)
    return Box(float(values["x1"]), float(values["y1"]), float(values["x2"]), float(values["y2"]),
               int(float(values.get("w", 0))), int(float(values.get("h", 0))))
