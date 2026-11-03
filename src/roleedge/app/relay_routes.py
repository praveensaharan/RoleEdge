"""Family relay routes: a grandchild and their grandparent talk through the app, with the caregiver watching over.

* ``POST /api/circles/{id}/relay``: one of them says something for the other (typed, or a voice recording, which the
  listener also hears in the speaker's own voice). Only between the parent and a child: the caregiver has their own
  channel. ``reply_to`` links an answer to the question; ``about`` links a question to the Studio pack it came from.
* The relay item is published at once (stage "writing", so the sender sees it go), then written for the listener and
  checked (``studio.relay``). It reaches the listener when the checks pass; anything held waits for the caregiver.
* For a child, a picture of what the grandparent described is drawn with Muse Image (about $0.01), only next to the
  real Meta provider; tests and offline runs never call it.
"""

from __future__ import annotations

import asyncio
from collections.abc import Awaitable, Callable
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool

from ..llm import LLM
from ..llm.meta import MetaProvider
from ..llm.meta_media import MetaMedia
from ..models import Circle, GateResult, Member, ThreadItem, TraceStep
from ..store import Store, new_id, now_iso
from ..studio import pass_on
from ..studio.relay import PICTURE_STYLE, check
from .audio import to_wav
from .guards import Budget
from .studio_routes import MAX_FILE_BYTES, UPLOAD_TYPES, UPLOADS

MAX_SAID_CHARS = 1000


class RelayRuns:
    def __init__(self, *, llm: LLM, store: Store, media: MetaMedia | None,
                 publish: Callable[[ThreadItem], Awaitable[ThreadItem]]) -> None:
        self.llm, self.store, self.media, self.publish = llm, store, media, publish
        self.tasks: set[asyncio.Task] = set()
        self.draws = media is not None and isinstance(llm.provider, MetaProvider)

    @staticmethod
    def pair(circle: Circle, speaker_id: str, to: str, reply_to: ThreadItem | None) -> tuple[Member, Member]:
        """(speaker, listener): a child and their grandparent, in either direction."""
        speaker = circle.recipient(speaker_id)
        if speaker is None:
            raise HTTPException(400, "That person isn't in this circle.")
        if speaker.role == "child":
            listener = circle.parent
        else:
            target = to or (reply_to.payload.get("from", "") if reply_to else "")
            listener = circle.recipient(target) if target else None
            if listener is None or listener.role != "child":
                raise HTTPException(400, "A relay goes between a grandparent and a grandchild.")
        return speaker, listener

    async def heard(self, circle: Circle, speaker: Member, audio: UploadFile, item_id: str) -> tuple[str, str, float]:
        """(transcript, saved recording url, seconds) for a voice relay."""
        if self.media is None:
            raise HTTPException(503, "Voice needs META_API_KEY (Muse Voice Transcribe). Type it instead.")
        content_type = (audio.content_type or "").split(";")[0].strip().lower()
        if not content_type.startswith("audio/") or content_type not in UPLOAD_TYPES:
            raise HTTPException(415, "Send a voice recording.")
        data = await audio.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, "That recording is too long.")
        wav = await run_in_threadpool(to_wav, data, 16000, 120)
        heard = await run_in_threadpool(self.media.transcribe, wav, [speaker.language_name], [circle.caregiver.local_name])
        if not heard.text.strip():
            raise HTTPException(422, "Nothing was heard. Hold the button while speaking.")
        folder = UPLOADS / item_id
        folder.mkdir(parents=True, exist_ok=True)
        path = folder / f"voice{UPLOAD_TYPES[content_type]}"
        path.write_bytes(data)
        return heard.text.strip(), f"/uploads/{item_id}/{path.name}", heard.duration_s

    def background(self, coro: Awaitable[None]) -> None:
        task = asyncio.ensure_future(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    async def write(self, circle: Circle, item: ThreadItem, speaker: Member, listener: Member) -> None:
        """Write it for the listener, check it, draw the picture for a child, then deliver it (or hold it)."""
        said = item.payload["text"]
        try:
            relay = await run_in_threadpool(pass_on, self.llm, circle, speaker, listener, said, item.id)
        except Exception as exc:  # never stuck in "writing": the caregiver gets to read it instead
            latest = self.store.item(item.id) or item
            latest.payload.update(stage="ready", message={"spoken_text": said, "screen_title": "", "steps": [],
                                                          "quick_replies": [], "english_gloss": ""})
            latest.gate = GateResult(passed=False, reasons=[f"It couldn't be checked ({type(exc).__name__}). Read it first."],
                                     rules=["unchecked"])
            latest.status = "held"
            await self.publish(latest)
            return
        extra: dict[str, Any] = {}
        trace = list(relay.trace)
        if listener.role == "child" and relay.gate.passed and relay.message.picture_en and self.draws:
            try:
                picture = await run_in_threadpool(self.media.generate_image,  # type: ignore[union-attr]
                                                  PICTURE_STYLE.format(scene=relay.message.picture_en))
                folder = UPLOADS / item.id
                folder.mkdir(parents=True, exist_ok=True)
                (folder / "picture.png").write_bytes(picture)
                extra["picture"] = f"/uploads/{item.id}/picture.png"
                trace.append(TraceStep(step="Drew a picture of it for the child", engine="meta/muse-image-1.0"))
            except Exception as exc:
                trace.append(TraceStep(step=f"No picture this time ({type(exc).__name__})", engine="code"))
        latest = self.store.item(item.id) or item
        latest.payload.update(stage="ready", **relay.payload(), **extra)
        latest.gate = relay.gate
        latest.status = "sent" if relay.gate.passed else "held"
        latest.trace.extend(trace)
        await self.publish(latest)


def add_relay_routes(app: FastAPI, *, llm: LLM, store: Store, media: MetaMedia | None, budget: Budget,
                     publish: Callable[[ThreadItem], Awaitable[ThreadItem]],
                     circle_or_404: Callable[[str], Circle], item_or_404: Callable[[str], ThreadItem]) -> RelayRuns:
    runs = RelayRuns(llm=llm, store=store, media=media, publish=publish)
    app.state.relay_gate = lambda item, allow_soft: check(item.payload, item.payload.get("text", ""), allow_soft)

    @app.post("/api/circles/{circle_id}/relay")
    async def relay(circle_id: str, speaker: Annotated[str, Form(alias="from")], text: Annotated[str, Form()] = "",
                    to: Annotated[str, Form()] = "", reply_to: Annotated[str, Form()] = "",
                    about: Annotated[str, Form()] = "", audio: Annotated[UploadFile | None, File()] = None) -> dict:
        circle = circle_or_404(circle_id)
        answering = item_or_404(reply_to) if reply_to else None
        if answering is not None and (answering.kind != "relay" or answering.circle_id != circle_id):
            raise HTTPException(400, "That isn't a relay in this circle.")
        if about and (pack := store.item(about)) is not None and pack.circle_id != circle_id:
            raise HTTPException(400, "That pack isn't in this circle.")
        from_member, listener = runs.pair(circle, speaker.strip(), to.strip(), answering)
        if answering is not None and answering.payload.get("recipient") != from_member.id:
            raise HTTPException(400, "Only the person it was for can answer it.")
        if not (text.strip() or audio):
            raise HTTPException(400, "Say or type something first.")
        budget.take()
        item_id = new_id("it")
        said, url, seconds = text.strip()[:MAX_SAID_CHARS], None, 0.0
        if audio is not None:
            said, url, seconds = await runs.heard(circle, from_member, audio, item_id)
        item = ThreadItem(
            id=item_id, circle_id=circle_id, at=now_iso(), kind="relay", speaker="person", status="draft",
            to="child" if listener.role == "child" else "parent",
            payload={"stage": "writing", "from": from_member.id, "recipient": listener.id, "text": said[:MAX_SAID_CHARS],
                     "audio": url, "seconds": round(seconds, 1), "reply_to": reply_to or None, "about": about or None,
                     "language": listener.language},
            trace=[TraceStep(step=f"{from_member.call_name} said something for {listener.call_name}"
                                  + (f" ({seconds:.0f}s, transcribed)" if url else ""),
                             engine="meta/muse-voice-transcribe-1.0" if url else "her phone")])
        await publish(item)
        runs.background(runs.write(circle, item, from_member, listener))
        return item.model_dump()

    return runs
