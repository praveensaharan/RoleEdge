"""Studio routes: share anything -> research swarm -> proposed plan -> chosen moments made -> checked -> sent.

A share is for the parent (the default) or one of the caregiver's children (payload["recipient"]), and each person
has their own four moments (``formats_for``); a child's pack also passes a child-safety review before it can be
approved. A share moves through payload["stage"]: researching ->
planned -> making -> ready (or failed). The swarm runs in
worker threads; ``StudioRuns`` is the one place that starts it, guards it and saves its progress:

* **Guards (the demo may be public):** one share in progress per circle (reserved before the first await, so two
  requests can't both slip in), a global rate limit, a Meta spend cap, and uploads checked for type, count and size
  before anything is counted. Uploads are served with ``nosniff`` and a sandbox policy, and only photo, video and
  audio types are accepted (no SVG, which could carry script). Links go through an SSRF guard (``studio.inputs``).
* **Thread safety:** agent events from worker threads are applied on the event loop thread only.
* **No lost updates:** progress is merged into the latest stored copy of the share, so a discard or her
  engagement that happened meanwhile is never overwritten; a discarded share stays discarded.
* **Apps:** a share can also be an item from a connected app (``connectors``: Notion, and the demo Gmail, Slack,
  Google Photos and Zoom accounts), passed as ``ref`` ("gmail:<id>"); it is read on the server and treated as data
  like everything else (a photo goes to the reader as a picture).
* **Never stuck:** any failure marks the share failed with a reason, and shares interrupted by a restart are
  marked failed when the app starts.
"""

from __future__ import annotations

import asyncio
import mimetypes
import re
from collections.abc import Awaitable, Callable, Iterator
from contextlib import contextmanager
from dataclasses import asdict
from pathlib import Path
from typing import Annotated, Any

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from ..compose import read_intent
from ..config import APP_WEB_DIR, LEDGER_FILE, OUTPUT_DIR
from ..connectors import Connector
from ..content.ingest import spread_frames
from ..content.social import fetch_social, is_social
from ..costs import spend
from ..llm import LLM
from ..llm.meta import MetaProvider
from ..llm.meta_media import MetaMedia
from ..models import Circle, GateResult, Member, ThreadItem, TraceStep
from ..models.studio import AgentEvent, ChildCheck, ExplainPlan, Format, PackReview, Research, StudioEngagement
from ..render.icons import ICONS
from ..store import Store, new_id, now_iso
from ..studio import Source, Swarm, check_pack, formats_for, link_text
from ..studio.relay import PICTURE_STYLE as CHILD_PICTURE_STYLE
from ..studio.swarm import MAX_IMAGES
from ..studio.verify import CHILD_RULE, VERIFIER_RULE
from .audio import file_to_wav
from .connect_routes import ConnectedApps
from .guards import Budget
from .hub import Hub

UPLOADS = OUTPUT_DIR / "uploads"
UPLOAD_TYPES = {  # what a phone or browser shares, and the extension it is stored under
    "image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp", "image/gif": ".gif",
    "video/mp4": ".mp4", "video/quicktime": ".mov", "video/webm": ".webm",
    "audio/webm": ".webm", "audio/ogg": ".ogg", "audio/mpeg": ".mp3", "audio/mp4": ".m4a", "audio/x-m4a": ".m4a",
    "audio/aac": ".aac", "audio/wav": ".wav", "audio/x-wav": ".wav",
}
MAX_FILES, MAX_FILE_BYTES = 6, 50_000_000  # a 90-second reel can be 30-40 MB
MAX_SOURCE_CHARS = 40_000  # kept whole for the date check: the agents saw all of it
MAX_QUICK_CHARS = 600  # typed words up to this long are read for intent first; a longer text is something to explain
IN_PROGRESS = ("researching", "making")
REF = re.compile(r"([a-z]+):([A-Za-z0-9_-]{1,64})")  # "<app>:<item id>"
DEMO_THUMB = re.compile(r"/assets/demo/photos/[a-z]+/[a-z0-9_-]+\.jpg")  # a demo album photo's preview, nothing else
STARTS_PER_MINUTE = 6  # across all circles: enough for a demo, too few to burn the credits
PARENT_PICTURE_STYLE = ("A warm, clear illustration in soft flat colours, calm and friendly, for an older reader. No "
                        "text, letters, numbers, logos, screens or real people's faces. Scene: {scene}")


class UploadFiles(StaticFiles):
    """Shared files, served so a browser never runs them: no type sniffing, and a sandbox if opened directly."""

    async def get_response(self, path: str, scope):  # type: ignore[override]
        response = await super().get_response(path, scope)
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Content-Security-Policy"] = "default-src 'none'; sandbox"
        return response


class MakeRequest(BaseModel):
    formats: list[Format]


class StudioRuns:
    def __init__(self, *, llm: LLM, store: Store, hub: Hub, media: MetaMedia | None, spend_cap_usd: float,
                 publish: Callable[[ThreadItem], Awaitable[ThreadItem]], context_line: Callable[[ThreadItem], str],
                 connectors: ConnectedApps | dict[str, Connector] | None = None) -> None:
        self.llm, self.store, self.hub, self.media = llm, store, hub, media
        # each family's own accounts where connected, else the demo ones (connect_routes.ConnectedApps)
        self.connectors = connectors if isinstance(connectors, ConnectedApps) else ConnectedApps(connectors or {})
        self.spend_cap_usd = spend_cap_usd
        self.publish, self.context_line = publish, context_line
        self.tasks: set[asyncio.Task] = set()  # references, so running shares aren't garbage-collected
        self.starts = Budget(per_minute=STARTS_PER_MINUTE, spend_cap_usd=spend_cap_usd, what="shares",
                             ledger_file=getattr(llm, "ledger_file", LEDGER_FILE))
        self.starting: set[str] = set()  # circles with a share between "accepted" and "saved"

    # ---------------------------------------------------------------- guards

    def busy(self, circle_id: str) -> bool:
        if circle_id in self.starting:
            return True
        return any(i.kind == "studio" and i.payload.get("stage") in IN_PROGRESS and not i.payload.get("discarded")
                   for i in self.store.items(circle_id))

    @contextmanager
    def start(self, circle_id: str) -> Iterator[None]:
        """Reserve the circle and one start from the minute's allowance; both are given back if the share is refused
        on the way (an upload too large, say). Runs synchronously up to the yield, so no other request interleaves."""
        if self.busy(circle_id):
            raise HTTPException(429, "Another share is still being prepared. Try again when it's ready.")
        stamp = self.starts.take()
        self.starting.add(circle_id)
        try:
            yield
        except BaseException:
            self.starts.give_back(stamp)
            raise
        finally:
            self.starting.discard(circle_id)

    @staticmethod
    def upload_types(files: list[UploadFile]) -> list[str]:
        """The content type of each file, or 413/415 before anything is read or counted."""
        if len(files) > MAX_FILES:
            raise HTTPException(413, f"Share at most {MAX_FILES} files at a time.")
        types = []
        for upload in files:
            declared = (upload.content_type or mimetypes.guess_type(upload.filename or "")[0] or "").split(";")[0].strip().lower()
            if declared not in UPLOAD_TYPES:
                raise HTTPException(415, "Share photos (JPEG, PNG, WebP, GIF), videos or voice notes only.")
            types.append(declared)
        return types

    async def save_uploads(self, item_id: str, files: list[UploadFile], types: list[str]) -> list[tuple[Path, str]]:
        saved = []
        for k, (upload, content_type) in enumerate(zip(files, types, strict=True)):
            data = await upload.read(MAX_FILE_BYTES + 1)
            if len(data) > MAX_FILE_BYTES:
                raise HTTPException(413, f"Each file can be at most {MAX_FILE_BYTES // 1_000_000} MB.")
            folder = UPLOADS / item_id
            folder.mkdir(parents=True, exist_ok=True)
            path = folder / f"file{k}{UPLOAD_TYPES[content_type]}"  # never the sender's name or extension
            path.write_bytes(data)
            saved.append((path, content_type))
        return saved

    # ---------------------------------------------------------------- plumbing

    def background(self, coro: Awaitable[None]) -> None:
        task = asyncio.ensure_future(coro)
        self.tasks.add(task)
        task.add_done_callback(self.tasks.discard)

    def emitter(self, circle_id: str, events: list[dict[str, Any]]) -> Callable[[AgentEvent], None]:
        """An emit() for worker threads: on the event loop thread, the event is broadcast and also stored, so a reload
        in the middle of a run still shows which agents have finished."""
        loop = asyncio.get_running_loop()

        def on_loop(event: AgentEvent) -> None:
            events.append(event.model_dump())
            item = self.store.item(event.item_id)
            if item is not None and not item.payload.get("discarded"):
                item.payload["agents"] = list(events)
                self.store.save_item(item)
            self.background(self.hub.send(circle_id, {"type": "agent", "event": event.model_dump()}))

        return lambda event: loop.call_soon_threadsafe(on_loop, event)

    async def save(self, item_id: str, payload: dict[str, Any], trace: list[TraceStep] = (), gate: GateResult | None = None,
                   status: str | None = None) -> ThreadItem | None:
        """Merge progress into the latest stored copy; a share discarded meanwhile stays discarded."""
        item = self.store.item(item_id)
        if item is None or item.payload.get("discarded"):
            return None
        item.payload.update(payload)
        item.trace.extend(trace)
        if gate is not None:
            item.gate = gate
        if status is not None:
            item.status = status  # type: ignore[assignment]
        return await self.publish(item)

    def recover_interrupted(self) -> None:
        for circle in self.store.circles():
            for item in self.store.items(circle.id):
                if item.kind == "studio" and item.payload.get("stage") in IN_PROGRESS:
                    if item.payload.get("adding") and item.payload.get("outputs"):  # adding a moment: the pack stays
                        item.payload.update(stage="ready", adding=[], error="Interrupted by a restart. Add the moment again.")
                    else:
                        item.payload.update(stage="failed", error="Interrupted by a restart. Share it again.")
                    self.store.save_item(item)

    # ---------------------------------------------------------------- research -> plan

    def history(self, circle: Circle, recipient: Member) -> str:
        """What this person did with earlier packs, for the audience agent."""
        lines = []
        for old in self.store.items(circle.id):
            if old.kind == "studio" and old.payload.get("engagement") and recipient_of(circle, old).id == recipient.id:
                done = [f"{e['format']}:{e['event']}" for e in old.payload["engagement"]]
                lines.append(f"- {old.payload.get('plan', {}).get('key_message_en', 'a pack')}: {', '.join(done[-8:])}")
        return "\n".join(lines[-6:]) or "No earlier packs yet."

    def recent(self, circle: Circle, recipient: Member) -> str:
        if recipient.role == "child":
            return f"{recipient.call_name} is {recipient.age}. No shared routines or recent conversation yet."
        lines = [self.context_line(i) for i in self.store.items(circle.id)[-8:] if i.kind in ("message", "reply", "summary")]
        routines = ", ".join(p.label for p in circle.playbooks if p.enabled)
        return f"Routines: {routines}\nRecent conversation:\n" + ("\n".join(lines) or "(none)")

    def check_ref(self, ref: str, circle: Circle | None = None) -> tuple[str, str] | None:
        """(app, item id) for a share from a connected app, or 400; None when there is no ref."""
        if not ref:
            return None
        match = REF.fullmatch(ref)
        connector = self.connectors.get(match.group(1), circle) if match else None
        if connector is None or not connector.status().connected:
            raise HTTPException(400, "That app isn't connected.")
        return match.group(1), match.group(2)

    async def read_source(self, circle: Circle, text: str, link: str, files: list[tuple[Path, str]],
                          ref: tuple[str, str] | None = None, item_id: str = "", swarm: Swarm | None = None) -> Source:
        parts = [text.strip()] if text.strip() else []
        files = list(files)
        images = [p for p, ct in files if ct.startswith("image/")]
        kind = "image" if images else "text"
        if ref:
            app, ref_id = ref
            connector = self.connectors.get(app, circle)
            kind = app
            try:
                title, body = await run_in_threadpool(connector.read, ref_id, circle)
                parts.append(f"From {connector.status().label}: {title}\n{body or '(the page is empty)'}")
                images += await run_in_threadpool(connector.images, ref_id, circle)  # a photo from an album
            except Exception:
                parts.append(f"(the {connector.status().label} item could not be read)")
        if link and is_social(link) and item_id:  # a reel or post link: the video itself, and its caption
            kind = "link"
            label = "Opened the link and saved the video"
            if swarm:
                swarm._event("download", label, "working", engine="yt-dlp")
            started = asyncio.get_running_loop().time()
            got = await run_in_threadpool(fetch_social, link, UPLOADS / item_id / "link")
            if got.video:
                files.append((got.video, "video/mp4"))
            said = "\n".join(x for x in (f"Posted by: {got.author}" if got.author else "",
                                         f"The post's caption: {got.caption}" if got.caption else "") if x)
            parts.append(f"Link: {link}\n{said or '(no caption)'}" + ("" if got.video else f"\n({got.problem})"))
            if swarm:
                swarm._event("download", label, "done" if got.video else "failed", engine="yt-dlp",
                             latency=round(asyncio.get_running_loop().time() - started, 2), detail=got.problem)
        elif link:
            kind = "link"
            page = await run_in_threadpool(link_text, link)
            parts.append(f"Link: {link}\n{page or '(the page could not be read: it may need a login, or not be a public web page)'}")
        video = None
        for path, ct in files:
            if ct.startswith("video/"):
                kind, video = "video", video or path
                images += await run_in_threadpool(spread_frames, path, path.parent / f"{path.stem}_frames", MAX_IMAGES)
            if ct.startswith(("video/", "audio/")) and self.media is not None:
                try:
                    heard = await run_in_threadpool(self.media.transcribe, await run_in_threadpool(file_to_wav, path))
                    if heard.text:
                        parts.append(f"Spoken in it: {heard.text}")
                    if ct.startswith("audio/") and kind == "text":
                        kind = "voice"
                except Exception:
                    parts.append("(the audio could not be transcribed)")
        return Source(kind=kind, text="\n\n".join(parts), images=images[:MAX_IMAGES], request=text.strip(), video=video,
                      moments_dir=video.parent / f"{video.stem}_moments" if video else None,
                      files_dir=UPLOADS / item_id / "found" if item_id else None)

    async def research(self, circle: Circle, recipient: Member, item_id: str, text: str, link: str,
                       files: list[tuple[Path, str]], ref: tuple[str, str] | None = None) -> None:
        events: list[dict[str, Any]] = []
        swarm = Swarm(self.llm, circle, item_id, emit=self.emitter(circle.id, events), recipient=recipient, media=self.media)
        try:
            source = await self.read_source(circle, text, link, files, ref, item_id=item_id, swarm=swarm)
            research = await run_in_threadpool(swarm.research, source, text, self.history(circle, recipient),
                                               self.recent(circle, recipient))
            for product in research.products:  # a saved picture becomes its URL; no server path leaves the server
                product.image = picture_url(Path(product.image)) if product.image else ""
            plan = await run_in_threadpool(swarm.plan, research, text)
            payload = {"stage": "planned", "source": {"kind": source.kind, "text": source.text[:MAX_SOURCE_CHARS],
                                                      "pictures": bool(source.images),
                                                      "picture_urls": [picture_url(p) for p in source.images]},
                       "research": research.model_dump(), "plan": plan.model_dump(),
                       # only the best moment is made unless more are picked: quicker and cheaper; more can be
                       # added afterwards, one by one (``make`` on a ready pack)
                       "formats": [f.format for f in plan.formats if f.recommended][:1]}
        except Exception as exc:
            payload = {"stage": "failed", "error": f"The agents couldn't finish: {str(exc)[:200]}"}
        await asyncio.sleep(0)  # let the last agent events land first
        await self.save(item_id, {**payload, "agents": events}, trace=swarm.trace)

    # ---------------------------------------------------------------- make -> check

    async def make(self, circle: Circle, item: ThreadItem, formats: list[Format], earlier: dict[str, Any] | None = None) -> None:
        """Make ``formats``, verify them and run the gate. ``earlier``: a ready pack's moments and review, when more
        moments are added to it; only the new ones are made and verified, then the gate reads them all."""
        events = list(item.payload.get("agents", []))
        swarm = Swarm(self.llm, circle, item.id, emit=self.emitter(circle.id, events), recipient=recipient_of(circle, item))
        back = earlier or {}
        try:
            research = Research.model_validate(item.payload["research"])
            plan = ExplainPlan.model_validate(item.payload["plan"])
            outputs = await run_in_threadpool(swarm.make, research, plan, formats)
        except Exception as exc:
            await self.save(item.id, {**back, "adding": [], "agents": events, "error": "The new moment couldn't be made. Try again."}
                            if earlier else {"stage": "failed", "error": f"The formats couldn't be made: {str(exc)[:200]}",
                                             "agents": events}, trace=swarm.trace)
            return
        await asyncio.sleep(0)
        if not outputs:
            await self.save(item.id, {**back, "adding": [], "agents": events, "error": "The new moment couldn't be made. Try again."}
                            if earlier else {"stage": "failed", "error": "None of the formats could be made. Try again.",
                                             "agents": events}, trace=swarm.trace)
            return
        frames = (item.payload.get("source") or {}).get("picture_urls") or []
        if "video" in outputs and any(frames):  # the scenes can show the shared video's own pictures
            outputs["video"]["frames"] = frames
            outputs["video"]["focus"] = (item.payload.get("research") or {}).get("focus") or []  # what to watch (SAM 3.1)
        extra: dict[str, Any] = {}
        if swarm.for_child:
            starter = (item.payload.get("plan") or {}).get("conversation_starter", "")
            extra["guardian"] = (await run_in_threadpool(swarm.guard, outputs, [starter])).model_dump()
        # the verifier reads the whole pack while the picture (if any) is drawn
        review, _ = await asyncio.gather(run_in_threadpool(swarm.verify, research, plan, outputs),
                                         self.draw(swarm, item.id, outputs))
        extra["review"] = review.model_dump()
        if back.get("review"):  # the earlier moments' review still stands; the pack is approved only if both are
            old = back["review"]
            extra["review"] = {**extra["review"], "faithful": old["faithful"] and review.faithful,
                               "right_for_reader": old["right_for_reader"] and review.right_for_reader,
                               "safe": old["safe"] and review.safe, "issues": [*old["issues"], *extra["review"]["issues"]]}
        if back.get("guardian") and extra.get("guardian"):  # the same for a child's pack: safe only if both parts are
            extra["guardian"] = {"safe_for_child": back["guardian"]["safe_for_child"] and extra["guardian"]["safe_for_child"],
                                 "concerns_en": [*back["guardian"]["concerns_en"], *extra["guardian"]["concerns_en"]]}
        outputs = {**back.get("outputs", {}), **outputs}
        await asyncio.sleep(0)
        gate = self.gate(item, outputs, guardian=extra.get("guardian"), review=extra["review"])
        check = TraceStep(step="Checked dates against the source and ran the final send gate: "
                          + ("passed" if gate.passed else "; ".join(gate.reasons)), engine="code")
        already_hers = bool(earlier) and item.status in ("sent", "played")
        if already_hers and not gate.passed:  # she keeps what she has; the new moment isn't added
            await self.save(item.id, {**back, "adding": [], "agents": events,
                                      "error": "The new moment was held, so it wasn't added: " + "; ".join(gate.reasons)},
                            trace=[*swarm.trace, check])
            return
        status = "held" if not gate.passed else item.status if already_hers else "sent" if circle.send_immediately else "draft"
        made = list(dict.fromkeys([*(item.payload.get("formats") or []), *formats])) if earlier else formats
        await self.save(item.id, {"stage": "ready", "outputs": outputs, "agents": events, "formats": made, "adding": [],
                                  "error": "", **extra}, trace=[*swarm.trace, check], gate=gate, status=status)

    async def draw(self, swarm: Swarm, item_id: str, outputs: dict[str, Any]) -> None:
        """The picture moment: Muse Image draws the maker's scene (about $0.01). Without Meta, or if it fails, the
        picture shows its caption with an icon instead."""
        picture = outputs.get("picture")
        if not picture:
            return
        picture["image"] = ""
        if self.media is None or not isinstance(self.llm.provider, MetaProvider):
            return
        label = "Drawing the picture"
        style = CHILD_PICTURE_STYLE if swarm.for_child else PARENT_PICTURE_STYLE
        swarm._event("illustrator", label, "working", engine="meta/muse-image-1.0")
        started = asyncio.get_running_loop().time()
        try:
            data = await run_in_threadpool(self.media.generate_image, style.format(scene=picture["prompt_en"][:600]))
        except Exception as exc:
            swarm._event("illustrator", label, "failed", detail=str(exc)[:200], engine="meta/muse-image-1.0")
            return
        folder = UPLOADS / item_id
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "picture-moment.png").write_bytes(data)
        picture["image"] = f"/uploads/{item_id}/picture-moment.png"
        latency = round(asyncio.get_running_loop().time() - started, 2)
        swarm._event("illustrator", label, "done", latency=latency, engine="meta/muse-image-1.0")
        swarm.trace.append(TraceStep(step=label, engine="meta/muse-image-1.0", latency_s=latency))

    @staticmethod
    def gate(item: ThreadItem, outputs: dict[str, Any], allow_soft: bool = False,
             guardian: dict[str, Any] | None = None, review: dict[str, Any] | None = None) -> GateResult:
        """The code checks before she sees a pack: everything shown to her (the formats and the plan's conversation
        starter) goes through the send gate, and every date in it must be in what was shared. The reader's own list
        of dates only counts for photos and videos, where there is no text to check against; otherwise a model could
        vouch for a date it invented."""
        source = item.payload.get("source") or {}
        plan = item.payload.get("plan") or {}
        reading = (item.payload.get("research") or {}).get("reading") or {}
        seen_in_pictures = reading.get("dates_and_numbers", []) if source.get("pictures") else []
        warning = ((item.payload.get("research") or {}).get("fact_check") or {}).get("verdict") == "likely_scam_or_misleading"
        gate = check_pack(outputs, source.get("text", ""), seen_in_pictures,
                          also_shown=[plan.get("conversation_starter", "")], allow_soft=allow_soft, warning=warning)
        if allow_soft:
            return gate
        reasons, rules = list(gate.reasons), list(gate.rules)
        guardian = guardian or item.payload.get("guardian")
        if guardian and not ChildCheck.model_validate(guardian).safe_for_child:
            concerns = " ".join(guardian["concerns_en"]) or "Read it yourself before sending."
            reasons.append(f"The child-safety check flagged it: {concerns}")
            rules.append(CHILD_RULE)
        review = review or item.payload.get("review")
        if review and not (checked := PackReview.model_validate(review)).approved:
            fixes = [i.problem_en for i in checked.issues if i.severity == "fix"] or [checked.verdict_en]
            reasons.append("The verifier wants you to look first: " + " ".join(fixes))
            rules.append(VERIFIER_RULE)
        return GateResult(passed=not rules, reasons=reasons, rules=rules)


def recipient_of(circle: Circle, item: ThreadItem) -> Member:
    """Who a share is for (older shares, and anything unknown, are for the parent)."""
    return circle.recipient(item.payload.get("recipient", "")) or circle.parent


def picture_url(path: Path) -> str:
    """Where the browser finds a picture the reader saw: an upload or a video's frame, or a demo album photo."""
    for root, prefix in ((UPLOADS, "/uploads/"), (APP_WEB_DIR, "/assets/")):
        try:
            return prefix + path.resolve().relative_to(root.resolve()).as_posix()
        except ValueError:
            continue
    return ""


def add_studio_routes(app: FastAPI, *, llm: LLM, store: Store, hub: Hub, media: MetaMedia | None, spend_cap_usd: float,
                      publish: Callable[[ThreadItem], Awaitable[ThreadItem]],
                      circle_or_404: Callable[[str], Circle], item_or_404: Callable[[str], ThreadItem],
                      context_line: Callable[[ThreadItem], str], connectors: ConnectedApps | dict[str, Connector] | None = None) -> StudioRuns:
    runs = StudioRuns(llm=llm, store=store, hub=hub, media=media, spend_cap_usd=spend_cap_usd, publish=publish,
                      context_line=context_line, connectors=connectors)
    runs.recover_interrupted()
    app.state.studio_gate = runs.gate  # the approve route re-runs it

    @app.post("/api/circles/{circle_id}/studio")
    async def studio_start(circle_id: str, text: Annotated[str, Form()] = "", link: Annotated[str, Form()] = "",
                           to: Annotated[str, Form()] = "", ref: Annotated[str, Form()] = "",
                           ref_title: Annotated[str, Form()] = "", ref_thumb: Annotated[str, Form()] = "",
                           voice: Annotated[str, Form()] = "",
                           files: Annotated[list[UploadFile] | None, File()] = None) -> dict:
        circle = circle_or_404(circle_id)
        recipient = circle.recipient(to.strip())
        if recipient is None:
            raise HTTPException(400, "That person isn't in this circle.")
        files, text, link = files or [], text.strip()[:8000], link.strip()[:2000]
        source_ref = runs.check_ref(ref.strip(), circle)
        if not (text or link or files or source_ref):
            raise HTTPException(400, "Share a message, a link, a photo or a video first.")
        types = runs.upload_types(files)
        quick_message = getattr(app.state, "quick_message", None)
        if quick_message and text and not (link or files or source_ref) and recipient.role != "child" and len(text) <= MAX_QUICK_CHARS:
            # typed words only: first read what is meant. A message to pass on takes the fast way (one rewrite);
            # something to explain goes on to the research below.
            stamp = runs.starts.take()
            intent, step = await run_in_threadpool(read_intent, llm, circle, text)
            if intent.kind == "message":
                said = voice if voice in ("mine", "assistant") else circle.voice
                return (await quick_message(circle, text, said, first=[step])).model_dump()
            runs.starts.give_back(stamp)  # the research below takes its own start
        item_id = new_id("it")
        with runs.start(circle_id):
            saved = await runs.save_uploads(item_id, files, types)
            item = ThreadItem(id=item_id, circle_id=circle_id, at=now_iso(), kind="studio",
                              to="child" if recipient.role == "child" else "parent", speaker="person",
                              status="draft", voice=circle.voice,
                              payload={"stage": "researching", "request": text, "link": link, "recipient": recipient.id,
                                       "ref": {"app": source_ref[0], "id": source_ref[1], "title": ref_title.strip()[:200],
                                               "thumb": ref_thumb if DEMO_THUMB.fullmatch(ref_thumb) else ""}
                                       if source_ref else None,
                                       "files": [{"url": f"/uploads/{item_id}/{p.name}", "type": ct} for p, ct in saved],
                                       "language": recipient.language, "agents": [], "engagement": []})
            await publish(item)
        runs.background(runs.research(circle, recipient, item_id, text, link, saved, source_ref))
        return item.model_dump()

    @app.post("/api/items/{item_id}/studio/make")
    async def studio_make(item_id: str, req: MakeRequest) -> dict:
        item = item_or_404(item_id)
        stage = item.payload.get("stage")
        if item.kind != "studio" or item.payload.get("discarded") or stage not in ("planned", "ready"):
            raise HTTPException(409, "The plan isn't ready yet, or the moments are being made.")
        circle = circle_or_404(item.circle_id)
        made = set(item.payload.get("outputs") or {}) if stage == "ready" else set()
        formats = [f for f in formats_for(recipient_of(circle, item)) if f in req.formats and f not in made]
        if not formats:
            raise HTTPException(400, "Pick at least one moment that isn't made yet.")
        # a ready pack keeps its moments (and her copy) while the new ones are made
        earlier = ({k: item.payload.get(k) for k in ("outputs", "review", "guardian", "stage") if item.payload.get(k) is not None}
                   if stage == "ready" else None)
        item.payload.update(stage="making", adding=formats if earlier else [], **({} if earlier else {"formats": formats}))
        await publish(item)
        runs.background(runs.make(circle, item, formats, earlier))
        return item.model_dump()

    @app.post("/api/items/{item_id}/engagement")
    async def engagement(item_id: str, event: StudioEngagement) -> dict:
        item = item_or_404(item_id)
        if item.kind != "studio" or item.status not in ("sent", "played"):
            raise HTTPException(409, "Only packs she has received collect engagement.")
        log = item.payload.setdefault("engagement", [])
        if len(log) >= 500:  # a pack has a handful of milestones; this only stops a flood
            return item.model_dump()
        log.append({**event.model_dump(), "text": event.text[:500], "at": now_iso()})
        item.status = "played"
        return (await publish(item)).model_dump()

    @app.get("/api/connectors")
    def connector_list(circle: str = "") -> list[dict[str, Any]]:
        """Every app: the family's own account where they connected one (``own``), else the demo account."""
        return runs.connectors.statuses(circle_or_404(circle) if circle else None)

    @app.get("/api/connectors/{app_id}/items")
    async def connector_items(app_id: str, circle: str = "") -> list[dict[str, Any]]:
        family = circle_or_404(circle) if circle else None  # the demo accounts hold each circle's own data
        connector = runs.connectors.get(app_id, family)
        if connector is None or not connector.status().connected:
            raise HTTPException(409, "That app isn't connected.")
        try:
            return [asdict(i) for i in await run_in_threadpool(connector.recent, 12, family)]
        except Exception as exc:
            raise HTTPException(502, f"{connector.status().label} didn't answer. Try again.") from exc

    @app.get("/api/icons")
    def icons() -> dict[str, str]:
        return ICONS  # the line icons the cards use; the studio viewers draw the same set

    @app.get("/api/spend")
    def spend_meter() -> dict:
        return {**spend(), "studio_cap_usd": spend_cap_usd}

    app.mount("/uploads", UploadFiles(directory=UPLOADS, check_dir=False), name="uploads")
    return runs
