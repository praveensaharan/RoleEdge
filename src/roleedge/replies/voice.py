"""Voice features from one spoken reply, measured in code (no model): speaking pace, pauses and length.

These feed the trend engine's voice lines. Pace is words per minute for English and characters per minute for
Japanese (Japanese has no spaces), which is why the two baselines differ; each person is only ever compared with
herself.
"""

from __future__ import annotations

import array
import io
import math
import re
import wave
from dataclasses import dataclass

FRAME_MS = 30


@dataclass(frozen=True)
class VoiceFeatures:
    seconds: float  # speech from first to last voiced frame
    pause_ratio: float  # share of that span that is silence
    pace: float  # words (en) or characters (ja) per minute


def measure(wav_bytes: bytes, transcript: str, language: str) -> VoiceFeatures:
    with wave.open(io.BytesIO(wav_bytes)) as w:
        rate, width, channels = w.getframerate(), w.getsampwidth(), w.getnchannels()
        samples = array.array("h", w.readframes(w.getnframes()))
    if width != 2 or channels != 1:
        raise ValueError("expected mono 16-bit PCM")
    step = max(1, rate * FRAME_MS // 1000)
    energies = [math.sqrt(sum(s * s for s in samples[i:i + step]) / step) for i in range(0, len(samples) - step + 1, step)]
    if not energies:
        return VoiceFeatures(0.0, 0.0, 0.0)
    loud = sorted(energies)[int(len(energies) * 0.95)]
    threshold = max(200.0, loud * 0.12)
    voiced = [e >= threshold for e in energies]
    if not any(voiced):
        return VoiceFeatures(0.0, 0.0, 0.0)
    first, last = voiced.index(True), len(voiced) - 1 - voiced[::-1].index(True)
    span = voiced[first:last + 1]
    seconds = len(span) * FRAME_MS / 1000
    pause_ratio = span.count(False) / len(span)
    units = len(re.findall(r"\w+", transcript)) if language == "en" else len(re.sub(r"[\s、。,.!?！？「」]", "", transcript))
    pace = units / seconds * 60 if seconds > 0 else 0.0
    return VoiceFeatures(round(seconds, 1), round(pause_ratio, 3), round(pace, 1))
