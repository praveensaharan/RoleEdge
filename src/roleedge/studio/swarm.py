"""Runs the studio's agents as a small swarm and reports every step live.

    Read        reader (+ web search on the raw text, when there is enough of it)
    Understand  fact checker (verdict from the search), audience, context        all in parallel
    Plan        planner ──(the caregiver picks the moments)──>
    Make        one maker per moment, in parallel
    Verify      child guardian (for a child), then the verifier on Muse Wonder reads the whole pack;
                code then checks every date against the source and runs the final send gate

The planner only proposes; code keeps the plan to the recipient's own moments (``formats_for``) and tidies what
the makers return (a quiz question whose answer index is out of range is dropped, never shown). The verifier only
advises: anything it wants fixed becomes a soft hold the caregiver reads; it can never send or unblock anything.

``emit`` is called from worker threads with an ``AgentEvent`` for the live activity panel. Code decides the order,
what runs in parallel, and what happens when an agent fails; models only fill in their own schema.
"""

from __future__ import annotations

import json
import re
import time
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from PIL import Image
from pydantic import BaseModel

from ..content.ingest import frames_at, image_part, video_part
from ..guard import TunedGuard, tuned_guard_from_settings
from ..llm import LLM, Message
from ..llm.meta import MetaProvider
from ..llm.meta_media import MetaMedia
from ..models import Circle, Member, TraceStep
from ..models.studio import (
    AgentEvent,
    ChildCheck,
    ExplainPlan,
    FactCheck,
    Format,
    FormatChoice,
    ItemFact,
    ItemFacts,
    Link,
    PackReview,
    Product,
    Quiz,
    Research,
    ReviewIssue,
    SourceReading,
    VideoTimeline,
)
from .agents import (
    AUDIENCE,
    CHILD_GUARD,
    CONTEXT,
    FACT_CHECK,
    FACT_SEARCH,
    FORMAT_NAMES,
    ITEM_RESEARCHER,
    ITEM_SEARCH,
    MAKERS,
    PLANNER,
    READER,
    VERIFIER,
    WATCHER,
    Specialist,
    fields,
    formats_for,
)
from .inputs import link_text, page_image
from .verify import recipient_texts, robotic, without_emoji

Emit = Callable[[AgentEvent], None]
WORKERS = 8  # one maker per moment (up to seven) at once
MAX_IMAGES = 8  # photos, or frames spread across a video
EARLY_SEARCH_CHARS = 80  # enough text to search on before the reader is done
# A parent's first moment by the content's shape (one_idea, family_news and warning keep the planner's own choice)
SHAPE_FIRST: dict[str, Format] = {"list": "card", "steps": "steps", "movement": "video", "topic": "map"}
LOOKUP_KINDS = {"film", "show", "song", "book", "website", "app", "product", "place", "course"}  # what the item researcher looks up
LOOKUP_LABELS = {"film": "film", "show": "show", "song": "song", "book": "book", "website": "website", "app": "app", "product": "product",
                 "place": "place", "course": "course"}
MAX_LOOKUPS = 10
# The full set made from one share, as on the home page: one item becomes a mind map, slides, a quiz, an animated
# video and a picture (a child's set: a picture story, a quiz game, a video, a mind map and a picture). The shape's
# moment (or the planner's first) leads; at most six.
PACKS: dict[str, tuple[Format, ...]] = {"parent": ("map", "steps", "askme", "video", "picture"),
                                        "child": ("story", "quiz", "video", "map", "picture")}
PACK_MAX = 6
SHAPE_REASON = {"list": "A list to keep, one item per line.", "steps": "One step per screen, in order.",
                "movement": "The movement to watch, one step per scene.", "topic": "The idea in the middle, its parts around it."}
CONTENT_FIELD: dict[str, str] = {"note": "lines", "steps": "pages", "story": "pages", "card": "lines", "askme": "questions",
                                 "quiz": "questions", "map": "branches", "relay": "questions", "video": "scenes",
                                 "picture": "prompt_en"}  # empty = unusable


@dataclass
class Source:
    """What the caregiver shared, ready for the reader."""

    kind: str  # text, image, video, link, voice
    text: str  # their message, a link's page text, a transcript...
    images: list[Path] = field(default_factory=list)  # photos, or frames sampled from a video
    request: str = ""  # the caregiver's own words, also part of ``text``
    video: Path | None = None  # the video itself, for the watcher (Muse Spark reads it whole)
    moments_dir: Path | None = None  # where stills at the timeline's moments go (default: next to the video)
    files_dir: Path | None = None  # where other files the agents fetch go (product pictures); None: none fetched

    @property
    def searchable(self) -> bool:
        """Enough of the item itself (beyond the caregiver's request) to search the web on before the reader is done."""
        return len(self.text.replace(self.request, "", 1).strip()) >= EARLY_SEARCH_CHARS

    def parts(self) -> list[dict[str, Any]]:
        return [{"type": "text", "text": f"Shared ({self.kind}):\n{self.text or '(no text)'}"}] + \
               [image_part(p) for p in self.images[:MAX_IMAGES]]


@dataclass
class Swarm:
    llm: LLM
    circle: Circle
    item_id: str
    emit: Emit = lambda event: None  # noqa: E731
    recipient: Member | None = None  # who the pack is for; the parent when None
    trace: list[TraceStep] = field(default_factory=list)
    tuned_guard: TunedGuard | None = None  # the LoRA child guard on Modal; set from settings for real Meta runs
    media: MetaMedia | None = None  # SAM 3.1 marks what to watch in a movement's stills; skipped without it

    def __post_init__(self) -> None:
        # Only next to the real Meta provider: tests and offline fakes never wake a GPU, whatever .env says.
        if self.tuned_guard is None and isinstance(self.llm.provider, MetaProvider):
            self.tuned_guard = tuned_guard_from_settings()

    @property
    def fields(self) -> dict[str, str]:
        return fields(self.circle, self.recipient)

    @property
    def for_child(self) -> bool:
        return self.recipient is not None and self.recipient.role == "child"

    @property
    def moments(self) -> tuple[Format, ...]:
        return formats_for(self.recipient or self.circle.parent)

    # ---------------------------------------------------------------- one agent

    def run(self, agent: Specialist, user: str | list[dict[str, Any]], label: str | None = None,
            check: Callable[[BaseModel], str] | None = None) -> BaseModel:
        """Run one specialist. ``check`` returns a reason when a valid-looking answer is still unusable (e.g. empty)."""
        name = agent.id.split("/", 1)[1]
        label = (label or agent.label).format(**self.fields)
        model = agent.model if agent.model and self.llm.provider.name == "meta" else None  # Wonder is a Meta model
        engine = self.llm.engine_for(model)
        self._event(name, label, "working", engine=engine)
        messages: list[Message] = [{"role": "system", "content": agent.system.format(**self.fields)},
                                   {"role": "user", "content": user}]
        try:
            result = self.llm.complete_json(agent.id, messages, agent.schema, name, effort=agent.effort, model=model)
            value = agent.schema.model_validate(result.data)
            problem = check(value) if check else ""
            if problem:
                raise ValueError(problem)
        except Exception as exc:  # a failed agent is reported, never silent
            self._event(name, label, "failed", detail=str(exc)[:200], engine=engine)
            raise
        self._event(name, label, "done", latency=result.latency_s, engine=engine)
        self.trace.append(TraceStep(step=label, engine=engine, latency_s=result.latency_s, replayed=result.cached))
        return value

    def _event(self, agent: str, label: str, state: str, latency: float = 0.0, detail: str = "",
               engine: str | None = None) -> None:
        engine = engine or (self.llm.engine if state != "skipped" else "")
        self.emit(AgentEvent(item_id=self.item_id, agent=agent, label=label, state=state,  # type: ignore[arg-type]
                             engine=engine, latency_s=latency, detail=detail))

    # ---------------------------------------------------------------- research

    def research(self, source: Source, request: str, history: str, recent: str) -> Research:
        """A shared video is watched whole first (its timeline, and stills at the moments it names); then the reader;
        audience, context and the item researcher start as soon as it is done. With enough text, the web search starts
        at once on the raw text, alongside, instead of waiting for the reader's claims (saves its time)."""
        with ThreadPoolExecutor(WORKERS) as pool:
            early = pool.submit(self.web_search, source.text, []) if source.searchable else None
            timeline, nouns = self.watch(source)
            parts = source.parts()
            if timeline:
                parts.append({"type": "text", "text": "Timeline of the whole video, watched with its sound:\n"
                                                      + json.dumps(timeline.model_dump(), ensure_ascii=False)})
            focus = pool.submit(self.find_focus, source.images[:MAX_IMAGES], nouns) if any(nouns) else None
            reading: SourceReading = self.run(READER, parts + [  # type: ignore[assignment]
                {"type": "text", "text": f"What the sender wants: {request or 'help them understand it'}"}])
            brief = json.dumps(reading.model_dump(), ensure_ascii=False)
            audience = pool.submit(self.run, AUDIENCE, f"Item: {brief}\n\nWhat they engaged with before:\n{history}")
            context = pool.submit(self.run, CONTEXT, f"Item: {brief}\n\nCircle and recent conversation:\n{recent}")
            items = pool.submit(self.look_up, reading)
            notes = early.result() if early else self.web_search(reading.summary_en, reading.claims_to_check)
            fact = self.fact_check(reading, notes, pictures=len(source.images[:MAX_IMAGES]))
            found = items.result()
            products = product_pictures(found, source.files_dir) if found else []
            if any(not p.image for p in products):  # no shop picture: cut the product out of the reel's own stills
                products = self.product_crops(products, source.images[:MAX_IMAGES], reading.pictures_en, source.files_dir)
            return Research(reading=reading, fact_check=fact, audience=audience.result(),  # type: ignore[arg-type]
                            context=context.result(), timeline=timeline, items=found,  # type: ignore[arg-type]
                            focus=focus.result() if focus else [], links=useful_links(fact, found), products=products)

    # ---------------------------------------------------------------- the video, watched whole

    def watch(self, source: Source) -> tuple[VideoTimeline | None, list[str]]:
        """Muse Spark watches the whole video with its sound (order, timing and movements that a few frames miss);
        the pictures then become stills taken in the middle of its steps. Returns the timeline and, per still, the
        body part or thing to watch. Without a video, or off Meta, nothing changes."""
        if source.video is None or self.llm.provider.name != "meta":  # only Meta's models take a whole video
            return None, []
        try:
            part = video_part(source.video)
            timeline: VideoTimeline = self.run(WATCHER, [{"type": "text", "text": f"Shared ({source.kind}):\n{source.text[:3000]}"},  # type: ignore[assignment]
                                                          part])
        except Exception:
            return None, []  # the reader still has the frames
        segments = [g for g in timeline.segments if g.end_s >= g.start_s]
        if len(segments) > MAX_IMAGES:  # evenly chosen steps, first and last kept
            step = (len(segments) - 1) / (MAX_IMAGES - 1)
            segments = [segments[round(k * step)] for k in range(MAX_IMAGES)]
        if len(segments) >= 2:
            folder = source.moments_dir or source.video.parent / f"{source.video.stem}_moments"
            stills = frames_at(source.video, [(g.start_s + g.end_s) / 2 for g in segments], folder)
            if len(stills) == len(segments):
                source.images = stills
                return timeline, [g.focus_en.strip() for g in segments]
        return timeline, []

    def find_focus(self, stills: list[Path], nouns: list[str]) -> list[list[float]]:
        """SAM 3.1 finds the body part or thing to watch in each still (the largest match), so the video moment can
        point at it. A still with nothing to watch, or no match, gets []."""
        if self.media is None or self.llm.provider.name != "meta":
            return []
        label = "Marking what to watch in each still"
        self._event("focus", label, "working", engine="meta/sam-3.1")
        started = time.monotonic()

        def one(still: Path, noun: str) -> list[float]:
            if not noun:
                return []
            try:
                boxes = self.media.find(still.read_bytes(), noun, mime="image/jpeg")  # type: ignore[union-attr]
                b = max(boxes, key=lambda b: (b.x2 - b.x1) * (b.y2 - b.y1)) if boxes else None
                return [b.x1, b.y1, b.x2, b.y2, float(b.width), float(b.height)] if b and b.width and b.height else []
            except Exception:  # a still without a mark is fine; the video plays the same
                return []

        with ThreadPoolExecutor(WORKERS) as pool:
            found = list(pool.map(one, stills, nouns))
        latency = round(time.monotonic() - started, 2)
        marked = sum(1 for f in found if f)
        self._event("focus", label, "done", latency=latency, engine="meta/sam-3.1", detail=f"{marked} of {len(found)} stills")
        self.trace.append(TraceStep(step=f"{label}: {marked} of {len(found)}", engine="meta/sam-3.1", latency_s=latency))
        return found

    def product_crops(self, products: list[Product], stills: list[Path], pictures: list[str], folder: Path | None) -> list[Product]:
        """For a product with no shop picture: the still the reader saw it in (its name in that still's description),
        and SAM 3.1 finds the package in it (a bottle, a tube, a jar, a box); the crop becomes its picture."""
        if self.media is None or folder is None or self.llm.provider.name != "meta" or not stills:
            return products
        out = []
        for k, product in enumerate(products, start=1):
            words = [w for w in re.findall(r"\w+", product.name.lower()) if len(w) >= 3]
            still = next((stills[i] for i, line in enumerate(pictures[:len(stills)]) if words and any(w in line.lower() for w in words)), None)
            if product.image or still is None:
                out.append(product)
                continue
            box = None
            for noun in ("bottle", "tube", "jar", "box"):
                try:
                    found = self.media.find(still.read_bytes(), noun, mime="image/jpeg")
                except Exception:
                    break
                if found:
                    box = max(found, key=lambda b: (b.x2 - b.x1) * (b.y2 - b.y1))
                    break
            if box is None:
                out.append(product)
                continue
            with Image.open(still) as im:
                pad_x, pad_y = (box.x2 - box.x1) * 0.12, (box.y2 - box.y1) * 0.12
                crop = im.crop((max(0, int(box.x1 - pad_x)), max(0, int(box.y1 - pad_y)),
                                min(im.width, int(box.x2 + pad_x)), min(im.height, int(box.y2 + pad_y))))
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / f"product-{k}-reel.jpg"
                crop.convert("RGB").save(path, quality=88)
            self.trace.append(TraceStep(step=f"Cut {product.name} out of the reel (SAM 3.1)", engine="meta/sam-3.1"))
            out.append(product.model_copy(update={"image": str(path)}))
        return out

    # ---------------------------------------------------------------- the things it names, looked up

    def look_up(self, reading: SourceReading) -> list[ItemFact]:
        """Each named film, show, book, site, app, product, place or course looked up on the web, so a moment can say
        what each one is (a film's genre, year and rating; whether a site is free). Off Meta, or nothing named: []."""
        wanted = [i for i in reading.items if i.kind in LOOKUP_KINDS][:MAX_LOOKUPS]
        if not wanted or self.llm.provider.name != "meta":
            return []
        kinds = sorted({i.kind for i in wanted})
        kind_label = LOOKUP_LABELS.get(kinds[0], "thing it names") if len(kinds) == 1 else "thing it names"
        label = ITEM_RESEARCHER.label.format(kind_label=kind_label)
        self._event("item_researcher", label, "working")
        listed = "\n".join(f"- {i.name} ({i.kind})" for i in wanted)
        prompt = ITEM_SEARCH.format(kinds=", ".join(LOOKUP_LABELS.get(k, k) + "s" for k in kinds), summary=reading.summary_en[:1500],
                                    items=listed, **self.fields)
        try:
            turn = self.llm.tool_turn("studio/item_search", [{"role": "user", "content": prompt}], [{"type": "web_search"}],
                                      effort="low")
            facts: ItemFacts = self.run(Specialist(ITEM_RESEARCHER.id, label, ItemFacts, ITEM_RESEARCHER.system,  # type: ignore[assignment]
                                                   ITEM_RESEARCHER.effort),
                                        f"Items:\n{listed}\n\nResearch notes:\n{turn.data.content or '(no results)'}")
        except Exception as exc:
            self._event("item_researcher", label, "failed", detail=str(exc)[:200])
            return []
        return facts.items

    def web_search(self, item_text: str, claims: list[str]) -> str:
        """Meta's built-in web search over the item's claims (or, before the reader is done, its raw text)."""
        label = "Searching the web for the claims"
        if self.llm.provider.name != "meta" or not (claims or item_text.strip()):
            self._event("web_search", label, "skipped", detail="web search needs the Meta provider"
                        if self.llm.provider.name != "meta" else "no claims to check")
            return ""
        self._event("web_search", label, "working")
        listed = "\n".join(f"- {c}" for c in claims) or "- (find the main factual claims in the item and check them)"
        prompt = FACT_SEARCH.format(summary=item_text[:3000], claims=listed, **self.fields)
        try:
            turn = self.llm.tool_turn("studio/web_search", [{"role": "user", "content": prompt}],
                                      [{"type": "web_search"}], effort="low")
        except Exception as exc:
            self._event("web_search", label, "failed", detail=str(exc)[:200])
            return ""
        self._event("web_search", label, "done", latency=turn.latency_s)
        self.trace.append(TraceStep(step=label, engine=f"{self.llm.engine} + web_search", latency_s=turn.latency_s,
                                    replayed=turn.cached))
        return turn.data.content or ""

    def fact_check(self, reading: SourceReading, notes: str, pictures: int = 0) -> FactCheck:
        """A structured verdict from the reader's claims and the web-search notes ("unverified" without notes). The fact
        checker sees text only, so it is told when the reader looked at pictures: it must not say there was none."""
        claims = "\n".join(f"- {c}" for c in reading.claims_to_check) or "- (no specific claims)"
        seen = (f"The reader looked at {pictures} picture(s) of the item itself; its summary and facts include what they "
                "show (dates, times, places on a photographed page).\n" if pictures else "")
        return self.run(FACT_CHECK, f"{seen}Item: {reading.summary_en}\nFacts the reader found: {'; '.join(reading.facts_en)}\n"  # type: ignore[return-value]
                                    f"Claims:\n{claims}\n\nFact-check notes from web search:\n{notes or '(no search results)'}")

    # ---------------------------------------------------------------- plan and make

    def plan(self, research: Research, request: str) -> ExplainPlan:
        plan = self.run(PLANNER, f"What {self.circle.caregiver.call_name} wants: {request or 'help her understand it'}"
                                 f"\n\nResearch:\n{json.dumps(research.model_dump(), ensure_ascii=False)}")
        plan = ExplainPlan.model_validate(without_emoji(plan.model_dump()))
        return self.own_moments(plan)

    def own_moments(self, plan: ExplainPlan) -> ExplainPlan:
        """This person's moments, each once, and the set that is made: the full pack (``PACKS``), led by the moment
        the content's shape calls for (a list is a card, a method is steps, a movement is a video, a topic is a map;
        in the lab the planner, told this in words, still put a spoken note first for 40 of 41 reels, so code makes
        sure of it), or else by the planner's own first choice. Recommended means made; the caregiver can still
        leave any out before they are made."""
        chosen = {c.format: c for c in reversed(plan.formats) if c.format in self.moments}  # the first of each wins
        order = [f for f in dict.fromkeys(c.format for c in plan.formats) if f in chosen]
        choices = [chosen[f] for f in order] + [FormatChoice(format=f, recommended=False, reason_en="")
                                                for f in self.moments if f not in chosen]
        by_format = {c.format: c for c in choices}
        planner_first = next((c.format for c in choices if c.recommended), choices[0].format)
        lead = planner_first if self.for_child else SHAPE_FIRST.get(plan.content_shape, planner_first)
        pack = PACKS["child" if self.for_child else "parent"]
        made = [f for f in dict.fromkeys([lead, *pack]) if f in by_format][:PACK_MAX]
        for c in choices:
            c.recommended = c.format in made
            if c.recommended and not c.reason_en:
                c.reason_en = SHAPE_REASON.get(plan.content_shape, "") if c.format == lead else ""
        plan.formats = [by_format[f] for f in made] + [c for c in choices if c.format not in made]
        return plan

    def make(self, research: Research, plan: ExplainPlan, formats: list[Format]) -> dict[str, dict[str, Any]]:
        """One maker per format, in parallel. A failed maker leaves its format out; the others still arrive. Each
        maker knows what else is made with it, so the moments don't all say the same thing."""
        together = ", ".join(FORMAT_NAMES[f] for f in formats)
        brief = (f"Plan:\n{json.dumps(plan.model_dump(), ensure_ascii=False)}\n\n"
                 f"Research:\n{json.dumps(research.model_dump(), ensure_ascii=False)}\n\n"
                 f"Made together for {self.fields['name']}: {together}. Do this format's own job; don't repeat what the "
                 "others say in the same way.")
        outputs: dict[str, dict[str, Any]] = {}
        with ThreadPoolExecutor(WORKERS) as pool:
            futures = {f: pool.submit(self._make_one, f, brief) for f in formats}
            for fmt, future in futures.items():
                try:
                    outputs[fmt] = without_emoji(future.result().model_dump())
                except Exception:
                    continue
        return outputs

    def _make_one(self, fmt: Format, brief: str) -> BaseModel:
        """One maker; if code finds its answer unusable (empty, or a quiz whose marked answer isn't the one its own
        explanation gives), it gets one more try, told what was wrong."""
        agent = MAKERS[fmt]
        system = agent.system.replace("{format_name}", FORMAT_NAMES[fmt])
        spec = Specialist(agent.id, agent.label, agent.schema, system, agent.effort)
        try:
            value = self.run(spec, brief, check=lambda value: unusable(fmt, value))
        except ValueError as exc:
            value = self.run(spec, f"{brief}\n\nYour first answer could not be used: {exc}. Make it again without that problem.",
                             check=lambda value: unusable(fmt, value))
        habits = robotic(recipient_texts({fmt: value.model_dump()}))
        if not habits:
            return value
        # it sounds like a report about a reel: one rewrite in the family's voice, told exactly what to change
        try:
            again = self.run(spec, f"{brief}\n\nYour first answer sounded like a report, not {self.fields['caregiver_local']} talking: "
                                   + "; ".join(habits) + ". Write it again as the family's own message, telling the content "
                                   "itself, without those habits.", check=lambda value: unusable(fmt, value))
        except ValueError:
            return value
        return again if len(robotic(recipient_texts({fmt: again.model_dump()}))) < len(habits) else value

    # ---------------------------------------------------------------- the child guardian

    def guard(self, outputs: dict[str, dict[str, Any]], also_shown: list[str]) -> ChildCheck:
        """For a child: a reviewer reads every line the child will see or hear. The tuned guard (Llama Guard + LoRA
        on Modal) runs when it is deployed; otherwise, or if it doesn't answer, the Muse Spark guardian does. If
        neither can run, that is a concern too, so the pack is held for the parent rather than sent unchecked."""
        lines = [t for t in [*recipient_texts(outputs), *also_shown] if t]
        if self.tuned_guard is not None and (checked := self._tuned_check(lines)) is not None:
            return checked
        listing = "\n".join(f"- {t}" for t in lines)
        try:
            return self.run(CHILD_GUARD, f"The pack, line by line:\n{listing}")  # type: ignore[return-value]
        except Exception:
            return ChildCheck(safe_for_child=False,
                              concerns_en=["The child-safety check couldn't run. Read it yourself before sending."])

    def _tuned_check(self, lines: list[str]) -> ChildCheck | None:
        """Every line through the tuned guard; None if it isn't reachable (the caller falls back)."""
        guard = self.tuned_guard
        assert guard is not None
        label = CHILD_GUARD.label.format(**self.fields)
        self._event("child_guardian", label, "working", engine=guard.engine)
        started = time.monotonic()
        try:
            verdicts = guard.classify(lines, self.recipient.age if self.recipient else None,
                                      self.recipient.language if self.recipient else "")
        except Exception as exc:
            self.trace.append(TraceStep(step=f"Tuned child guard unavailable ({type(exc).__name__}); Muse Spark reviewed it",
                                        engine="code"))
            return None
        latency = round(time.monotonic() - started, 2)
        concerns = [f'"{line[:90]}": ' + (", ".join(v.names) if v.names else "not sure it is safe")
                    for line, v in zip(lines, verdicts, strict=True) if not v.safe]
        self._event("child_guardian", label, "done", latency=latency, engine=guard.engine)
        self.trace.append(TraceStep(step=f"{label} (tuned guard, {len(lines)} lines)", engine=guard.engine, latency_s=latency))
        return ChildCheck(safe_for_child=not concerns, concerns_en=concerns)


    # ---------------------------------------------------------------- the verifier

    def verify(self, research: Research, plan: ExplainPlan, outputs: dict[str, dict[str, Any]]) -> PackReview:
        """The whole pack read against the research before the caregiver sees it: Muse Wonder first; if it can't
        answer, Muse Spark does the same review. If neither can, that is a "fix" issue, so the pack waits for the
        caregiver to read it rather than looking checked."""
        shown = {f: {k: v for k, v in o.items() if not k.endswith("_en") and k not in ("image",)} for f, o in outputs.items()}
        brief = (f"Research:\n{json.dumps(research.model_dump(), ensure_ascii=False)}\n\n"
                 f"Plan:\n{json.dumps(plan.model_dump(), ensure_ascii=False)}\n\n"
                 f"The pack {self.fields['name']} will see and hear, by moment:\n{json.dumps(shown, ensure_ascii=False)}")
        try:
            return self.run(VERIFIER, brief)  # type: ignore[return-value]
        except Exception:
            pass
        if VERIFIER.model and self.llm.provider.name == "meta":  # Wonder didn't answer: the default model reviews
            fallback = Specialist(VERIFIER.id, "Verifying the whole pack (Muse Spark, Wonder didn't answer)",
                                  VERIFIER.schema, VERIFIER.system, VERIFIER.effort)
            try:
                return self.run(fallback, brief)  # type: ignore[return-value]
            except Exception:
                pass
        return PackReview(faithful=True, right_for_reader=True, safe=True, verdict_en="The verifier couldn't run.",
                          issues=[ReviewIssue(format="pack", severity="fix",
                                              problem_en="The verifier couldn't run. Read it yourself before sending.")])


# ---------------------------------------------------------------- links and products, by code

LINK_KINDS = {"website", "app", "course", "book", "show"}  # products: the family buys them for her; no shop link
PLATFORMS = {"youtube", "google", "instagram", "tiktok", "facebook", "amazon", "netflix", "spotify", "apple"}
NOT_A_DESTINATION = re.compile(r"(^|\.)(bit\.ly|tinyurl\.com|t\.co|goo\.gl|ow\.ly|instagram\.com|tiktok\.com|facebook\.com|"
                               r"fb\.watch|linktr\.ee|example\.(com|org))$", re.I)


def useful_links(fact: FactCheck, items: list[ItemFact]) -> list[Link]:
    """Up to three links worth giving her, only for a genuine item (confirmed, or not disproved and with no scam signs):
    the official pages the item researcher found for the sites, apps, classes, books and shows it names. Never from a
    model's own words, never a shortener, a social profile or a platform's front page, one per site."""
    if fact.verdict not in ("looks_genuine", "unverified") or fact.scam_signs and fact.verdict != "looks_genuine":
        return []
    out: list[Link] = []
    for item in items:
        url = secure((item.source_url or "").strip()) if item.kind in LINK_KINDS else ""
        parts = urlsplit(url)
        host = (parts.hostname or "").lower().removeprefix("www.")
        front_page = parts.path in ("", "/") and host.split(".")[0] in PLATFORMS
        if item.kind not in LINK_KINDS or not url.startswith("https://") or not host or NOT_A_DESTINATION.search(host) or front_page:
            continue
        if host not in {link.host for link in out}:
            out.append(Link(title=item.name, url=url, host=host))
    return out[:3]


def secure(url: str) -> str:
    """An https link: as found, or an http one upgraded when its site answers over https; else ""."""
    if url.startswith("https://"):
        return url
    if url.startswith("http://"):
        upgraded = "https://" + url[len("http://"):]
        return upgraded if link_text(upgraded, deadline_s=8.0) else ""
    return ""


def product_pictures(items: list[ItemFact], folder: Path | None) -> list[Product]:
    """Each product it recommends with what it is good for, and its picture from the shop's page (og:image), saved
    in ``folder``; no folder, or no picture found: the product without one."""
    products = [i for i in items if i.kind == "product"][:6]
    out = []
    for k, item in enumerate(products, start=1):
        image = ""
        if folder is not None and item.source_url.startswith(("https://", "http://")):
            got = page_image(item.source_url)
            if got:
                data, ext = got
                folder.mkdir(parents=True, exist_ok=True)
                path = folder / f"product-{k}.{ext}"
                path.write_bytes(data)
                image = str(path)
        out.append(Product(name=item.name, good_for_en=item.what_en or item.detail_en, image=image))
    return out


def unusable(fmt: Format, value: BaseModel) -> str:
    """Why a maker's valid-looking answer can't be shown, or "": empty, or a quiz question whose marked answer is not
    the one its explanation gives (in the lab one marked the reel's false claim as right while explaining it was false)."""
    if not getattr(tidy(value), CONTENT_FIELD[fmt]):
        return "it came back empty"
    if isinstance(value, Quiz):
        for q in value.questions:
            if not answer_explained(q.choices, q.answer, q.explain):
                return f'question "{q.question}" marks "{q.choices[q.answer]}" as right, but its explanation gives another answer'
    return ""


def _words(text: str) -> set[str]:
    return {w for w in re.findall(r"\w+", text.lower()) if len(w) >= 3}


def answer_explained(choices: list[str], answer: int, explain: str) -> bool:
    """The explanation shares more words with the marked choice than with any other (ties pass: a short or
    yes/no choice can't be told apart this way, and the verifier still reads it)."""
    said = _words(explain)
    overlap = [len(_words(c) & said) for c in choices]
    return overlap[answer] >= max(overlap)


def tidy(value: BaseModel) -> BaseModel:
    """Drop what a viewer can't show: a quiz question needs 2-4 choices and an answer index among them."""
    if isinstance(value, Quiz):
        value.questions = [q for q in value.questions if 2 <= len(q.choices) <= 4 and 0 <= q.answer < len(q.choices)]
    return value
