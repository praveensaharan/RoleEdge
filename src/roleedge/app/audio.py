"""Convert a browser recording (WebM/Opus, MP4/AAC, ...) to the WAV that Muse Voice Transcribe accepts."""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path

MAX_SECONDS = 600  # a voice note or a short video; longer input is cut, so a small file can't decode to gigabytes


def to_wav(data: bytes, rate: int = 16000, max_seconds: int = MAX_SECONDS) -> bytes:
    """Mono, 16-bit PCM WAV at ``rate`` Hz, via ffmpeg (the format the transcription API documents), at most
    ``max_seconds`` long. The input goes through a temporary file, not a pipe: an MP4 from a phone usually keeps its
    index at the end, which ffmpeg can only reach in a file it can seek ("partial file" otherwise)."""
    with tempfile.TemporaryDirectory() as tmp:
        source = Path(tmp) / "input"
        source.write_bytes(data)
        return file_to_wav(source, rate, max_seconds)


def file_to_wav(path: Path, rate: int = 16000, max_seconds: int = MAX_SECONDS) -> bytes:
    """``to_wav`` for a file already on disk (a shared reel), without reading it into memory first."""
    result = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-i", str(path), "-t", str(max_seconds),
                             "-vn", "-ac", "1", "-ar", str(rate),
                             "-c:a", "pcm_s16le", "-map_metadata", "-1", "-f", "wav", "pipe:1"],
                            capture_output=True, timeout=60, check=False)
    if result.returncode != 0 or len(result.stdout) < 100:
        raise ValueError(f"could not read the recording: {result.stderr.decode(errors='replace')[:200]}")
    return result.stdout


# ---------------------------------------------------------------- your own voice, made a little clearer

MAX_VOICE_SECONDS = 180  # a voice message to her, not a talk
# Plain signal processing, no AI model (tuned on a distant-microphone recording: -39 LUFS before, -18 after):
# rumble off, steady room noise reduced, a little less boxiness and a little more presence, phrase-to-phrase level
# evened out, then a gentle compressor.
_CLEARER = ("highpass=f=80,afftdn=nr=12:nf=-55:tn=1,equalizer=f=250:t=q:w=1.2:g=-2,equalizer=f=3500:t=q:w=1.5:g=3,"
            "dynaudnorm=f=200:g=11:p=0.9:m=18,acompressor=threshold=0.1:ratio=2.5:attack=8:release=150")
_TARGET = "I=-18:TP=-1.5:LRA=7"  # spoken-word loudness, the level of a podcast or a phone's voice memo
# after the level is set: the room tail in the pauses lowered (at most 10 dB), pauses longer than a second
# shortened, and the silence before and after trimmed
_AFTER = ("agate=threshold=0.02:ratio=2:range=0.3:attack=10:release=250:knee=4,"
          "silenceremove=stop_periods=-1:stop_duration=1.0:stop_threshold=-42dB:stop_silence=0.7,"
          "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.15,areverse,"
          "silenceremove=start_periods=1:start_threshold=-45dB:start_silence=0.25,areverse")


@dataclass
class CleanVoice:
    data: bytes  # AAC in an .m4a, which every browser plays
    seconds: float
    before_lufs: float
    after_lufs: float


def clean_voice(path: Path, max_seconds: int = MAX_VOICE_SECONDS) -> CleanVoice:
    """Your recording (any audio or video file), made clearer for her: louder and even, less noise, long pauses
    shortened. Two passes, so the loudness is measured first and then set exactly (EBU R128)."""
    head = ["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-t", str(max_seconds), "-vn", "-ac", "1"]
    measured = _run([*head, "-af", f"ebur128=framelog=quiet,{_CLEARER},loudnorm={_TARGET}:print_format=json",
                     "-f", "null", "-"]).stderr.decode(errors="replace")
    found = re.search(r"\{[^{}]*\"input_i\"[^{}]*\}", measured)
    before = re.findall(r"^\s+I:\s+(-?[\d.]+|-inf) LUFS", measured, re.M)
    if not found:
        raise ValueError("could not read the recording")
    m = json.loads(found.group(0))
    if m["input_i"] in ("-inf", "inf") or float(m["input_i"]) < -70:
        raise ValueError("nothing was heard in the recording")
    level = (f"loudnorm={_TARGET}:measured_I={m['input_i']}:measured_TP={m['input_tp']}:measured_LRA={m['input_lra']}"
             f":measured_thresh={m['input_thresh']}:offset={m['target_offset']}:linear=true")
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "voice.m4a"
        _run([*head, "-af", f"{_CLEARER},{level},{_AFTER}", "-ar", "44100", "-c:a", "aac", "-b:a", "96k",
              "-movflags", "+faststart", "-map_metadata", "-1", str(out)])
        after = _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(out), "-af", "ebur128=framelog=quiet",
                      "-f", "null", "-"]).stderr.decode(errors="replace")
        seconds = _run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(out)]).stdout
        loud = re.findall(r"^\s+I:\s+(-?[\d.]+) LUFS", after, re.M)
        return CleanVoice(data=out.read_bytes(), seconds=round(float(seconds.strip() or 0), 1),
                          before_lufs=float(before[-1]) if before and before[-1] != "-inf" else -70.0,
                          after_lufs=float(loud[-1]) if loud else -18.0)


def plain_voice(path: Path, max_seconds: int = MAX_VOICE_SECONDS) -> bytes:
    """The same recording as it was, only re-encoded so every browser plays it (to hear before and after)."""
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "original.m4a"
        _run(["ffmpeg", "-hide_banner", "-nostats", "-i", str(path), "-t", str(max_seconds), "-vn", "-ac", "1",
              "-ar", "44100", "-c:a", "aac", "-b:a", "96k", "-movflags", "+faststart", "-map_metadata", "-1", str(out)])
        return out.read_bytes()


def _run(cmd: list[str]) -> subprocess.CompletedProcess:
    result = subprocess.run(cmd, capture_output=True, timeout=120, check=False)
    if result.returncode != 0:
        raise ValueError(f"could not read the recording: {result.stderr.decode(errors='replace')[-200:]}")
    return result
