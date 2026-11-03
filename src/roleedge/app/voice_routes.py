"""Your own voice on a message: you record it (or pick a recording) and she hears you, not a device voice.

No voice model makes or changes the voice. The organisers ruled that every model called at runtime must be a Meta
model, and Meta has no text-to-speech or voice-cloning model, so a cloned voice isn't an option. Your real voice
is also more natural than any clone. Code makes the recording clearer (``audio.clean_voice``: ffmpeg filters, no AI):
louder and even, rumble and steady noise reduced, long pauses shortened, silence trimmed. Muse Voice Transcribe
writes down what you said, for her captions. The final send gate then checks those words, like any other message
to her, before the recording is attached.
"""

from __future__ import annotations

import re
import tempfile
import unicodedata
from collections import Counter
from collections.abc import Awaitable, Callable
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from ..gates import check_outgoing
from ..llm.meta_media import MetaMedia
from ..models import Circle, ThreadItem, TraceStep
from ..store import now_iso
from .audio import MAX_VOICE_SECONDS, clean_voice, plain_voice, to_wav
from .guards import Budget
from .studio_routes import MAX_FILE_BYTES, UPLOADS

SAME_WORDS = 0.85  # this much of the approved message heard in the recording: her captions show the approved words


def words_heard(approved: str, heard: str) -> float:
    """How much of the approved message is in what was heard, 0 to 1 (words; characters for Japanese)."""
    def tokens(text: str) -> list[str]:
        text = unicodedata.normalize("NFKC", text).lower()
        if re.search(r"[぀-ヿ一-鿿]", text):
            return [ch for ch in text if ch.isalnum()]
        return re.findall(r"[a-z0-9']+", text)
    want, got = Counter(tokens(approved)), Counter(tokens(heard))
    total = sum(want.values())
    return round(sum((want & got).values()) / total, 2) if total else 0.0


def add_voice_routes(app: FastAPI, *, media: MetaMedia | None, budget: Budget,
                     publish: Callable[[ThreadItem], Awaitable[ThreadItem]],
                     circle_or_404: Callable[[str], Circle], item_or_404: Callable[[str], ThreadItem]) -> None:

    def own_message(item_id: str) -> ThreadItem:
        item = item_or_404(item_id)
        if item.kind != "message" or item.to != "parent" or item.payload.get("ack") or "message" not in item.payload:
            raise HTTPException(400, "Only your own messages to her can carry your voice.")
        if item.status in ("played", "done"):
            raise HTTPException(409, "She has already heard this one." if item.status == "played" else "This one was discarded.")
        return item

    @app.post("/api/items/{item_id}/own-voice")
    async def own_voice(item_id: str, audio: UploadFile) -> dict:
        item = own_message(item_id)
        circle = circle_or_404(item.circle_id)
        if media is None:
            raise HTTPException(503, "Your voice needs META_API_KEY (Muse Voice Transcribe writes her captions).")
        budget.take()
        with tempfile.TemporaryDirectory() as tmp:
            source = Path(tmp) / "recording"
            with source.open("wb") as fh:  # to disk, not memory: a phone video keeps its index at the end
                size = 0
                while chunk := await audio.read(1 << 20):
                    size += len(chunk)
                    if size > MAX_FILE_BYTES:
                        raise HTTPException(413, f"That recording is too big. Keep it under {MAX_VOICE_SECONDS // 60} minutes.")
                    fh.write(chunk)
            try:
                clear = await run_in_threadpool(clean_voice, source)
                original = await run_in_threadpool(plain_voice, source)
            except ValueError as exc:
                raise HTTPException(422, f"That recording didn't work: {exc}.") from exc
        if clear.seconds < 1:
            raise HTTPException(422, "Nothing was heard. Speak a little closer to the microphone.")
        wav = await run_in_threadpool(to_wav, clear.data)
        languages = list(dict.fromkeys([circle.parent.language_name, circle.caregiver.language_name]))
        heard = await run_in_threadpool(media.transcribe, wav, languages, [circle.parent.call_name, circle.caregiver.call_name])
        if not heard.text:
            raise HTTPException(422, "Nothing was heard. Speak a little closer to the microphone.")
        gate = check_outgoing(heard.text)  # what she will actually hear goes through the same final gate
        if not gate.passed:
            raise HTTPException(422, "This recording can't be sent from the app: " + "; ".join(gate.reasons))

        approved = item.payload["message"]["spoken_text"]
        match = words_heard(approved, heard.text)
        version = int((item.payload.get("own_voice") or {}).get("version", 0)) + 1
        folder = UPLOADS / item.id
        folder.mkdir(parents=True, exist_ok=True)
        for old in folder.glob("voice-*.m4a"):
            old.unlink()
        (folder / f"voice-{version}.m4a").write_bytes(clear.data)
        (folder / f"voice-{version}-original.m4a").write_bytes(original)
        item.payload["own_voice"] = {
            "audio": f"/uploads/{item.id}/voice-{version}.m4a", "original": f"/uploads/{item.id}/voice-{version}-original.m4a",
            "seconds": clear.seconds, "heard": heard.text, "match": match, "version": version, "at": now_iso(),
            # her captions: the approved words when you said them, else exactly what you said
            "caption": approved if match >= SAME_WORDS else heard.text,
            "before_lufs": clear.before_lufs, "after_lufs": clear.after_lufs}
        item.speaker, item.voice = "person", "mine"
        item.trace += [
            TraceStep(step=f"Made your recording clearer ({clear.seconds:.0f}s): level {clear.before_lufs:.0f} to "
                           f"{clear.after_lufs:.0f} LUFS, noise and long pauses reduced", engine="code (ffmpeg)"),
            TraceStep(step=f"Wrote down what you said for her captions ({match:.0%} of the message)",
                      engine="meta/muse-voice-transcribe-1.0", latency_s=heard.latency_s),
            TraceStep(step="Final send gate on your recorded words: passed", engine="code")]
        return (await publish(item)).model_dump()

    @app.delete("/api/items/{item_id}/own-voice")
    async def remove_own_voice(item_id: str) -> dict:
        item = own_message(item_id)
        if item.payload.pop("own_voice", None) is not None:
            for old in (UPLOADS / item.id).glob("voice-*.m4a"):
                old.unlink()
            item.trace.append(TraceStep(step="Removed your recording: the device voice reads it", engine="you"))
        return (await publish(item)).model_dump()
