"""HTTP and WebSocket API for the two screens.

Flows:
* **Compose:** caregiver text -> composer (model) -> final send gate (code) -> draft, held, or sent at once.
* **Approve:** the caregiver approves a draft (or overrides a soft hold); the gate runs again before sending.
* **Reply:** the parent's reply -> reply reader (model) + red-flag check (code) -> a summary for the caregiver, an
  acknowledgement for her, and an urgent alert to both if needed. Her signals are stored for the trend engine.
* **Trends:** the trend engine (code) over the stored six weeks.

Run:  roleedge serve      (or: uvicorn roleedge.app.server:create_app --factory)
"""

from __future__ import annotations

import asyncio
import json
import shutil
from datetime import datetime
from typing import Literal
from urllib.parse import urlencode
from zoneinfo import ZoneInfo

from fastapi import FastAPI, HTTPException, Request, UploadFile, WebSocket, WebSocketDisconnect
from fastapi.concurrency import run_in_threadpool
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..compose import compose
from ..config import APP_WEB_DIR, OUTPUT_DIR, get_settings
from ..errands.demo_accounts import app_connectors
from ..families import CIRCLES, SUPPORT_CENTRES, history
from ..gates import check_outgoing
from ..llm import LLM, pipeline_provider
from ..llm.meta_media import MetaMedia
from ..models import Circle, GateResult, ParentMessage, ThreadItem, TraceStep, VoiceChoice, VoiceDay
from ..models.studio import FORMATS
from ..replies import read_reply
from ..replies.voice import VoiceFeatures, measure
from ..store import Store, new_id, now_iso
from ..trends import InsightsMode, build_report
from .audio import to_wav
from .connect_routes import ConnectedApps, add_connect_routes
from .copy import CAREGIVER_ALERT, PARENT_TEXT
from .errand_routes import add_errand_routes
from .guards import Budget
from .hub import Hub
from .lab_routes import add_lab_routes
from .relay_routes import add_relay_routes
from .studio_routes import MAX_FILE_BYTES, MAX_FILES, UPLOADS, add_studio_routes
from .voice_routes import add_voice_routes

MAX_BODY_BYTES = MAX_FILES * MAX_FILE_BYTES + 1_000_000  # the largest share, plus its form fields
QUICK_PER_MINUTE = 30  # compose and replies: one model call each


class ComposeRequest(BaseModel):
    text: str
    voice: VoiceChoice | None = None


class ApproveRequest(BaseModel):
    allow_soft: bool = False


class ReplyRequest(BaseModel):
    text: str


class SettingsRequest(BaseModel):
    voice: VoiceChoice | None = None
    send_immediately: bool | None = None
    avatar_mode: Literal["3d", "2d"] | None = None


def create_app(llm: LLM | None = None, store: Store | None = None, insights: InsightsMode = "full",
               media: MetaMedia | None = None) -> FastAPI:
    llm = llm or LLM(pipeline_provider())
    if media is None and (meta := get_settings().meta):
        media = MetaMedia(meta)
    store = store or Store()
    if not store.circles():
        store.reset(CIRCLES.values(), history)
    hub = Hub()
    app = FastAPI(title="RoleEdge")
    quick = Budget(per_minute=QUICK_PER_MINUTE, spend_cap_usd=get_settings().studio_spend_cap_usd, what="messages",
                   ledger_file=llm.ledger_file)

    @app.middleware("http")
    async def refuse_huge_bodies(request: Request, call_next):  # noqa: ANN001, ANN202
        """Refuse an oversized upload from its declared length, before it is written to disk."""
        length = request.headers.get("content-length", "")
        if length.isdigit() and int(length) > MAX_BODY_BYTES:
            return JSONResponse({"detail": "That's too much to share at once."}, status_code=413)
        return await call_next(request)

    def circle_or_404(circle_id: str) -> Circle:
        circle = store.circle(circle_id)
        if circle is None:
            raise HTTPException(404, f"No circle '{circle_id}'.")
        return circle

    def item_or_404(item_id: str) -> ThreadItem:
        item = store.item(item_id)
        if item is None:
            raise HTTPException(404, f"No item '{item_id}'.")
        return item

    async def publish(item: ThreadItem) -> ThreadItem:
        store.save_item(item)
        await hub.send(item.circle_id, {"type": "item", "item": item.model_dump()})
        return item

    def gate_message(message: ParentMessage, allow_soft: bool = False, heard: str = "") -> GateResult:
        """``heard``: the words of your own recording, when one is attached (she hears those, not the text)."""
        return check_outgoing(message.spoken_text, message.screen_title, *message.steps, *message.quick_replies, heard,
                              allow_soft=allow_soft)

    # ---------------------------------------------------------------- read

    @app.get("/api/circles")
    def circles() -> list[dict]:
        return [{"id": c.id, "label": c.label, "parent": c.parent.call_name, "language": c.parent.language}
                for c in store.circles()]

    @app.get("/api/circles/{circle_id}")
    def circle_detail(circle_id: str) -> dict:
        circle = circle_or_404(circle_id)
        return {"circle": circle.model_dump(), "items": [i.model_dump() for i in store.items(circle_id)],
                "engine": llm.engine}

    @app.get("/api/circles/{circle_id}/trends")
    def trends(circle_id: str) -> dict:
        circle_or_404(circle_id)
        report = build_report(circle_id, store.events(circle_id), store.voice_days(circle_id), mode=insights,
                              support_centre=SUPPORT_CENTRES.get(circle_id))
        return report.model_dump()

    # ---------------------------------------------------------------- caregiver -> parent

    @app.patch("/api/circles/{circle_id}/settings")
    def settings(circle_id: str, req: SettingsRequest) -> dict:
        circle = circle_or_404(circle_id)
        if req.voice is not None:
            circle.voice = req.voice
        if req.send_immediately is not None:
            circle.send_immediately = req.send_immediately
        if req.avatar_mode is not None:
            circle.avatar_mode = req.avatar_mode
        store.save_circle(circle)
        return circle.model_dump()

    async def quick_message(circle: Circle, text: str, voice: VoiceChoice, first: list[TraceStep] | None = None) -> ThreadItem:
        """One rewrite in her words, then the send gate: the fast way (also what a typed message to pass on takes
        from the Studio, after ``read_intent``)."""
        message, step = await run_in_threadpool(compose, llm, circle, text, voice)
        gate = gate_message(message)
        status = "held" if not gate.passed else "sent" if circle.send_immediately else "draft"
        trace = [*(first or []), step,
                 TraceStep(step="Final send gate: " + ("passed" if gate.passed else "; ".join(gate.reasons)), engine="code")]
        item = ThreadItem(id=new_id("it"), circle_id=circle.id, at=now_iso(), kind="message", to="parent",
                          speaker="person" if voice == "mine" else "assistant", status=status, voice=voice,
                          payload={"source_text": text, "message": message.model_dump(),
                                   "language": circle.parent.language}, gate=gate, trace=trace)
        return await publish(item)

    app.state.quick_message = quick_message

    @app.post("/api/circles/{circle_id}/compose")
    async def compose_message(circle_id: str, req: ComposeRequest) -> dict:
        circle = circle_or_404(circle_id)
        if not req.text.strip():
            raise HTTPException(400, "Write something first.")
        quick.take()
        return (await quick_message(circle, req.text, req.voice or circle.voice)).model_dump()

    @app.post("/api/items/{item_id}/approve")
    async def approve(item_id: str, req: ApproveRequest) -> dict:
        item = item_or_404(item_id)
        if item.status not in ("draft", "held"):
            raise HTTPException(409, f"This item is already {item.status}.")
        if item.kind == "studio":
            if item.payload.get("stage") != "ready":
                raise HTTPException(409, "The pack isn't ready yet.")
            gate = app.state.studio_gate(item, item.payload["outputs"], allow_soft=req.allow_soft)
        elif item.kind == "relay":
            if item.payload.get("stage") != "ready":
                raise HTTPException(409, "The relay is still being written.")
            gate = app.state.relay_gate(item, req.allow_soft)
        else:
            gate = gate_message(ParentMessage.model_validate(item.payload["message"]), allow_soft=req.allow_soft,
                                heard=(item.payload.get("own_voice") or {}).get("heard", ""))
        item.gate = gate
        if not gate.passed:
            item.status = "held"
            item.trace.append(TraceStep(step="Still held: " + "; ".join(gate.reasons), engine="code"))
            raise HTTPException(422, {"message": "This can't be sent from the app: " + "; ".join(gate.reasons),
                                      "item": (await publish(item)).model_dump()})
        item.status = "sent"
        item.trace.append(TraceStep(step="Approved by you" + (" (sent anyway)" if req.allow_soft else ""),
                                    engine="you"))
        return (await publish(item)).model_dump()

    @app.post("/api/items/{item_id}/discard")
    async def discard(item_id: str) -> dict:
        item = item_or_404(item_id)
        item.status = "done"
        item.payload["discarded"] = True
        return (await publish(item)).model_dump()

    # ---------------------------------------------------------------- parent's phone

    @app.post("/api/items/{item_id}/played")
    async def played(item_id: str) -> dict:
        item = item_or_404(item_id)
        if item.status == "sent":
            item.status = "played"
            item.trace.append(TraceStep(step="Played on her phone", engine="her phone"))
            await publish(item)
        return item.model_dump()

    async def handle_reply(circle: Circle, text: str, *, heard: list[TraceStep] | None = None,
                           voice: VoiceFeatures | None = None) -> list[dict]:
        circle_id = circle.id
        day = datetime.now(ZoneInfo(circle.parent.timezone)).date().isoformat()
        context = [_context_line(i) for i in store.items(circle_id)[-6:]]
        published = [await publish(ThreadItem(id=new_id("it"), circle_id=circle_id, at=now_iso(), kind="reply",
                                              to="caregiver", speaker="person", status="done",
                                              payload={"text": text, "spoken": voice is not None,
                                                       "voice": voice.__dict__ if voice else None},
                                              trace=heard or []))]
        if voice and voice.seconds >= 2:
            store.merge_voice_day(circle_id, VoiceDay(day=day, speech_rate_wpm=voice.pace, pause_ratio=voice.pause_ratio,
                                                      reply_seconds=voice.seconds))

        # The reply reader and the errand router read her words at the same time.
        result, (errand, routed) = await asyncio.gather(
            run_in_threadpool(read_reply, llm, circle, text, day=day, context=context),
            errands.route(circle, text, context))
        is_errand = errand is not None and errand.kind != "none"
        store.add_events(circle_id, result.events)
        reading = result.reading
        published.append(await publish(ThreadItem(
            id=new_id("it"), circle_id=circle_id, at=now_iso(), kind="summary", to="caregiver", speaker="assistant",
            status="done", payload={"summary": reading.summary_for_caregiver,
                                    "signals": [s.model_dump() for s in reading.signals],
                                    "needs": [n.model_dump() for n in reading.needs],
                                    "question": reading.question_for_caregiver, "alert": result.alert},
            trace=[*result.trace, TraceStep(step=f"Saved {len(result.events)} signals for her trend", engine="code")])))

        words = PARENT_TEXT[circle.parent.language]
        if result.alert == "urgent":
            quote = next((s.quote for s in reading.signals if s.kind in {"fall", "chest_pain", "breathless",
                                                                         "fainted", "confused"}), text)
            published.append(await publish(ThreadItem(
                id=new_id("it"), circle_id=circle_id, at=now_iso(), kind="alert", to="caregiver", speaker="assistant",
                status="done", payload={"text": CAREGIVER_ALERT.format(parent=circle.parent.call_name, quote=quote)},
                trace=[TraceStep(step="Urgent words found: alerted you at once", engine="code")])))
            number, caregiver = circle.parent.emergency_number, circle.caregiver.local_name
            alert = ParentMessage(spoken_text=words["alert_spoken"].format(caregiver=caregiver, number=number),
                                  screen_title=words["alert_title"].format(caregiver=caregiver), steps=[],
                                  quick_replies=[words["alert_button"].format(number=number)],
                                  english_gloss=PARENT_TEXT["en"]["alert_spoken"].format(caregiver=caregiver, number=number))
            published.append(await publish(ThreadItem(
                id=new_id("it"), circle_id=circle_id, at=now_iso(), kind="alert", to="parent", speaker="assistant",
                status="sent", voice="assistant", payload={"message": alert.model_dump(), "emergency": number,
                                                           "language": circle.parent.language},
                trace=[TraceStep(step="Showed the emergency number on her phone", engine="code")])))
        elif is_errand:
            await errands.handle(circle, errand, routed)  # she asked the assistant to find out or order something
        elif reading.reply_to_parent:
            ack = ParentMessage(spoken_text=reading.reply_to_parent, screen_title=words["ack_title"], steps=[],
                                quick_replies=[], english_gloss=reading.reply_to_parent_english)
            gate = gate_message(ack)
            published.append(await publish(ThreadItem(
                id=new_id("it"), circle_id=circle_id, at=now_iso(), kind="message", to="parent", speaker="assistant",
                status="sent" if gate.passed else "held", voice="assistant",
                payload={"message": ack.model_dump(), "language": circle.parent.language, "ack": True}, gate=gate,
                trace=[TraceStep(step="Acknowledged her reply (playbook)", engine=llm.engine),
                       TraceStep(step="Final send gate: " + ("passed" if gate.passed else "; ".join(gate.reasons)),
                                 engine="code")])))
        return [p.model_dump() for p in published]

    @app.post("/api/circles/{circle_id}/reply")
    async def reply(circle_id: str, req: ReplyRequest) -> list[dict]:
        circle = circle_or_404(circle_id)
        if not req.text.strip():
            raise HTTPException(400, "The reply is empty.")
        quick.take()
        return await handle_reply(circle, req.text.strip()[:4000])

    @app.post("/api/circles/{circle_id}/reply-audio")
    async def reply_audio(circle_id: str, audio: UploadFile) -> list[dict]:
        circle = circle_or_404(circle_id)
        if media is None:
            raise HTTPException(503, "Voice replies need META_API_KEY (Muse Voice Transcribe).")
        quick.take()
        data = await audio.read(MAX_FILE_BYTES + 1)
        if len(data) > MAX_FILE_BYTES:
            raise HTTPException(413, "That recording is too long.")
        wav = await run_in_threadpool(to_wav, data)
        language = circle.parent.language_name
        heard = await run_in_threadpool(media.transcribe, wav, [language], [circle.caregiver.local_name])
        if not heard.text:
            raise HTTPException(422, "Nothing was heard. Hold the button while speaking.")
        voice = await run_in_threadpool(measure, wav, heard.text, circle.parent.language)
        trace = [TraceStep(step=f"Transcribed her voice ({heard.duration_s:.0f}s, {language})",
                           engine="meta/muse-voice-transcribe-1.0", latency_s=heard.latency_s),
                 TraceStep(step=f"Measured pace {voice.pace:.0f}/min, pauses {voice.pause_ratio:.0%}", engine="code")]
        return await handle_reply(circle, heard.text, heard=trace, voice=voice)

    errands = add_errand_routes(app, llm=llm, store=store, publish=publish, budget=quick, circle_or_404=circle_or_404,
                                item_or_404=item_or_404)
    add_relay_routes(app, llm=llm, store=store, media=media, budget=quick, publish=publish, circle_or_404=circle_or_404,
                     item_or_404=item_or_404)
    # each family's own Gmail, Calendar and Notion where they connected them, else the prefilled demo accounts
    apps = ConnectedApps(app_connectors(get_settings().notion_token, added=errands.added), store, get_settings())
    errands.apps = apps
    add_connect_routes(app, apps=apps, store=store, settings=get_settings(), circle_or_404=circle_or_404)
    add_voice_routes(app, media=media, budget=quick, publish=publish, circle_or_404=circle_or_404, item_or_404=item_or_404)
    add_studio_routes(app, llm=llm, store=store, hub=hub, media=media, spend_cap_usd=get_settings().studio_spend_cap_usd,
                      publish=publish, circle_or_404=circle_or_404, item_or_404=item_or_404, context_line=_context_line,
                      connectors=apps)

    # ---------------------------------------------------------------- demo + live updates

    @app.post("/api/demo/reset")
    async def reset() -> dict:
        store.reset(CIRCLES.values(), history)
        shutil.rmtree(UPLOADS, ignore_errors=True)  # shared files go with the shares (retention: demo data only)
        return {"ok": True}

    @app.websocket("/ws/{circle_id}")
    async def live(socket: WebSocket, circle_id: str) -> None:
        if store.circle(circle_id) is None:
            await socket.close(code=4404)
            return
        await hub.join(circle_id, socket)
        try:
            while True:
                try:
                    message = json.loads(await socket.receive_text())
                except (ValueError, KeyError):  # not JSON, or a binary frame
                    continue
                # her phone reports what is on its screen; the caregiver's mirror follows it (F8, "see what they see")
                if isinstance(message, dict) and message.get("type") == "screen":
                    await hub.send(circle_id, {"type": "screen", "from": str(message.get("from", ""))[:40],
                                               "screen": screen_report(message.get("screen"))})
        except WebSocketDisconnect:
            pass
        finally:
            await hub.leave(circle_id, socket)

    # ---------------------------------------------------------------- pages

    @app.get("/", response_model=None)
    def home(circle: str | None = None) -> FileResponse | RedirectResponse:
        if circle:  # the Studio used to live here; keep its old links working
            return RedirectResponse(f"/studio?{urlencode({'circle': circle})}")
        return FileResponse(APP_WEB_DIR / "home.html")

    @app.get("/studio")
    def workspace() -> FileResponse:
        return FileResponse(APP_WEB_DIR / "index.html")

    @app.get("/phone/{circle_id}")
    def phone(circle_id: str) -> FileResponse:
        circle_or_404(circle_id)
        return FileResponse(APP_WEB_DIR / "phone.html")

    @app.get("/compare")
    def compare() -> FileResponse:
        return FileResponse(APP_WEB_DIR / "compare.html")  # build-time avatar comparison (see modal_apps/)

    app.mount("/compare-media", StaticFiles(directory=OUTPUT_DIR / "compare", check_dir=False), name="compare-media")
    add_lab_routes(app, APP_WEB_DIR)  # the Reel Lab's results (docs/REEL_LAB.md), read only
    app.mount("/assets", StaticFiles(directory=APP_WEB_DIR), name="assets")
    return app


def _context_line(item: ThreadItem) -> str:
    if item.kind == "relay":
        return f"family relay from {item.payload.get('from', '')}: {item.payload.get('text', '')}"
    who: Literal["caregiver", "parent", "assistant"] = (
        "assistant" if item.speaker == "assistant" else "caregiver" if item.to == "parent" else "parent")
    text = item.payload.get("text") or (item.payload.get("message") or {}).get("spoken_text") \
        or item.payload.get("summary") or ""
    return f"{who}: {text}"


def screen_report(screen: object) -> dict[str, str]:
    """Only the fields the mirror understands, in their expected shapes: the live channel can't relay anything else."""
    screen = screen if isinstance(screen, dict) else {}
    view = screen.get("view") if screen.get("view") in ("app", "sheet") else "app"
    fmt = screen.get("format") if screen.get("format") in FORMATS else ""
    item, member = (str(screen.get(key) or "")[:40] for key in ("item", "member"))
    safe = lambda value: value if value.replace("_", "").isalnum() else ""  # noqa: E731
    return {"view": view, "item": safe(item), "format": fmt, "member": safe(member)}
