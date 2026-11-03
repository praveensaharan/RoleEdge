"""Studio: what the research swarm finds, the explanation plan it proposes, and the moments it makes.

Whatever the caregiver shares is researched first, then turned into "moments" for one person: things to do with the
family, not documents to study. Each person has their own set, and each moment ends with something that comes back
to the caregiver (her answers, a question for her grandchild, how far she got):

* for the parent: **note** (in your words, read aloud), **steps** (slides: one step per screen), **map** (a mind
  map), **askme** (a gentle quiz; her answers come back), **video** (an animated video, narrated), **picture** (an
  illustration drawn by Muse Image) and **card** (a fridge card to keep);
* for a child: **story** (a picture story), **quiz** (a quiz game), **map** (a mind map to tap open), **video**,
  **picture** and **relay** (questions to ask their grandparent, passed on by the family relay).

Before the caregiver approves a pack, the verifier (Muse Wonder) reads all of it against the research
(``PackReview``); anything it wants fixed is a soft hold.

Field order is the order the model fills each object (rule A4). Text for the recipient is in their language;
``*_en`` fields are English for the caregiver.
"""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field

from .digest import IconName

Format = Literal["note", "steps", "card", "askme", "story", "quiz", "map", "relay", "video", "picture"]
# What the item is, by shape: it decides the first moment for a parent (``swarm.SHAPE_FIRST``)
ContentShape = Literal["list", "steps", "movement", "topic", "one_idea", "family_news", "warning"]
PARENT_FORMATS: tuple[Format, ...] = ("note", "steps", "map", "askme", "video", "picture", "card")
CHILD_FORMATS: tuple[Format, ...] = ("story", "quiz", "map", "video", "picture", "relay")
FORMATS: tuple[Format, ...] = tuple(dict.fromkeys(PARENT_FORMATS + CHILD_FORMATS))
SourceKind = Literal["text", "image", "video", "link", "voice"]
# "personal": the family's own news (a family photo, a message from family, the family's call), which the web can't
# confirm and needn't: it is taken as the caregiver shared it, never doubted in front of her
StudioVerdict = Literal["looks_genuine", "personal", "unverified", "likely_scam_or_misleading"]


# ---------------------------------------------------------------- research swarm


class Segment(BaseModel):
    start_s: float
    end_s: float
    shows_en: str  # what happens: the movement, the action, what is on screen
    said_en: str  # what is said in it, in English (translated if needed); "" if nothing
    on_screen_text: str  # words shown on screen, as written; "" if none
    focus_en: str  # for a movement or demonstration, the one body part or thing to watch ("mouth", "both hands"); "" if none


class VideoTimeline(BaseModel):
    """Watcher: the whole video watched in order (Muse Spark reads the video itself, not only a few frames)."""

    summary_en: str
    segments: list[Segment]  # in time order, one per step, movement, item or scene (at most 12)


ItemKind = Literal["film", "show", "song", "book", "website", "app", "product", "place", "course", "food", "person", "other"]


class NamedItem(BaseModel):
    name: str  # as written or said
    kind: ItemKind


class ItemFact(BaseModel):
    name: str
    kind: ItemKind
    what_en: str  # one plain line: what it is
    detail_en: str  # one useful fact: a film's year and genre, whether a site or app is free, where a place is
    suitable_en: str  # who it suits; a film's age rating or "for adults" when known; "" if unknown
    source_url: str  # "" if nothing reliable was found


class Link(BaseModel):
    """A link the app adds itself, only for a genuine item and only from what the research found (never model text)."""

    title: str
    url: str
    host: str


class Product(BaseModel):
    """A product the item recommends, with what it is good for and its picture from the shop's own page."""

    name: str
    good_for_en: str
    image: str = ""  # a file the app saved (served as a URL), "" if no picture was found


class ItemFacts(BaseModel):
    """Item researcher: each named thing in the item looked up on the web (films, sites, books, places...)."""

    items: list[ItemFact]


class SourceReading(BaseModel):
    """Reader: what was shared, in plain English for the caregiver."""

    kind_en: str  # e.g. "Instagram reel about a pension deadline"
    summary_en: str  # 2-3 sentences
    facts_en: list[str]  # facts stated in the source, quoted or closely paraphrased
    dates_and_numbers: list[str]  # every date, time, amount or number as written in the source
    claims_to_check: list[str]  # claims a careful person would verify before believing them
    pictures_en: list[str] = []  # what each attached picture shows, one short line each, in order (frames of a video)
    items: list[NamedItem] = []  # each named thing in a list or mentioned by name: films, sites, books, places...


class CheckedClaim(BaseModel):
    claim: str
    finding: str  # what the search found, one sentence
    source_url: str  # "" when nothing reliable was found


class FactCheck(BaseModel):
    """Fact checker: claims checked with web search; scam signs."""

    verdict: StudioVerdict
    checked: list[CheckedClaim]
    scam_signs: list[str]  # e.g. "asks for money urgently", "asks to keep it secret"
    note_en: str  # one sentence for the caregiver


class AudienceRead(BaseModel):
    """Audience: how this person takes things in, and what has worked before."""

    reads_as_en: str  # e.g. "81, reads slowly, prefers voice and big pictures"
    attention_seconds: int  # how long she will comfortably watch or listen
    best_formats: list[Format]  # most promising first
    interests_en: list[str]  # hooks that make it personal
    avoid_en: list[str]  # what would confuse, worry or bore her


class ContextNote(BaseModel):
    """Context: why this matters to her now, from the circle and recent conversation."""

    why_it_matters_en: str
    related_en: list[str]  # upcoming events, earlier messages, routines it touches
    conversation_hook_en: str  # something to talk about afterwards


class FormatChoice(BaseModel):
    format: Format
    recommended: bool
    reason_en: str  # one short sentence


class ExplainPlan(BaseModel):
    """Planner: the proposed way to explain it, shown to the caregiver before anything is made."""

    goal_en: str  # what the caregiver is trying to achieve
    content_shape: ContentShape = "one_idea"  # list, steps, movement (exercise), topic (with parts), one idea, news, warning
    key_message_en: str  # the one thing she should remember
    outline_en: list[str]  # 3-5 points, in order
    formats: list[FormatChoice]  # all of this person's moments, recommended ones first
    tone_en: str
    leave_out_en: list[str]
    conversation_starter: str  # a question for her, in her language
    conversation_starter_en: str
    safety_notes_en: list[str]  # e.g. "the reel's claim is unverified: say so"


# ---------------------------------------------------------------- the moments (makers)


class SpokenNote(BaseModel):
    """note: a few sentences in the caregiver's own words, read aloud on her phone."""

    title: str
    lines: list[str]  # 3-6 short sentences, first person, as the caregiver would say them
    question: str  # a question for her at the end
    summary_en: str


class Page(BaseModel):
    icon: IconName  # the picture on the page
    big_text: str  # 2-6 words
    line: str  # one or two short sentences, shown and read aloud


class Pages(BaseModel):
    """steps (one step per screen, at her pace) and story (a picture story for a child)."""

    title: str
    pages: list[Page]  # 3-6
    summary_en: str


class CardLine(BaseModel):
    icon: IconName
    text: str


class FridgeCard(BaseModel):
    """card: one page she keeps (the caregiver can print it)."""

    title: str
    lines: list[CardLine]  # 3-5
    remember: str  # the one date, time or thing to remember, copied from the source; "" if none
    ask: str  # who to ask if unsure, one short line
    summary_en: str


class QuizQuestion(BaseModel):
    icon: IconName
    question: str
    choices: list[str]  # 2-3 short choices
    answer: int  # index of the right choice
    explain: str  # one kind sentence with the right answer, shown after she answers


class Quiz(BaseModel):
    """askme (two gentle questions for her) and quiz (a quiz game for a child)."""

    title: str
    questions: list[QuizQuestion]
    summary_en: str


class Branch(BaseModel):
    icon: IconName
    label: str
    leaves: list[str]  # 0-3


class MindMap(BaseModel):
    """map: a mind map, the key idea in the middle and its parts around it, each tapped open."""

    root: str
    branches: list[Branch]  # 3-5
    summary_en: str


class RelayStarters(BaseModel):
    """relay: questions a child can ask their grandparent about it, sent by the family relay."""

    title: str
    intro: str  # one line inviting the child to ask
    questions: list[str]  # 2-3, in the child's own words
    summary_en: str


class Scene(BaseModel):
    icon: IconName  # the picture of the scene
    big_text: str  # 2-6 words on screen
    narration: str  # one or two short sentences, spoken while the scene plays
    frame: int = -1  # the shared video's own picture behind this scene (its number in the reading's pictures_en); -1 none


class AnimatedVideo(BaseModel):
    """video: a short animated video, 4-6 scenes, drawn and narrated on her phone (no rendering wait)."""

    title: str
    scenes: list[Scene]
    summary_en: str


class Picture(BaseModel):
    """picture: one illustration of the key idea, drawn by Muse Image, with a caption in her language."""

    title: str
    caption: str  # one or two short sentences, shown and read aloud
    prompt_en: str  # what to draw: a calm scene, no text, letters, logos or real people
    summary_en: str


MAKER_SCHEMAS: dict[Format, type[BaseModel]] = {
    "note": SpokenNote, "steps": Pages, "card": FridgeCard, "askme": Quiz,
    "story": Pages, "quiz": Quiz, "map": MindMap, "relay": RelayStarters,
    "video": AnimatedVideo, "picture": Picture,
}


class Research(BaseModel):
    """Everything the research swarm found, as stored on the studio item."""

    reading: SourceReading
    fact_check: FactCheck
    audience: AudienceRead
    context: ContextNote
    timeline: VideoTimeline | None = None  # a shared video, watched whole
    items: list[ItemFact] = []  # the named things it lists, looked up one by one
    focus: list[list[float]] = []  # per picture: the box of what to watch [x1, y1, x2, y2, w, h] (SAM 3.1), [] if none
    links: list[Link] = []  # checked links for a genuine item (an official page, a free class), added by code
    products: list[Product] = []  # the products it recommends, with their pictures


class ReviewIssue(BaseModel):
    format: str  # the moment it is in, or "pack"
    problem_en: str  # one sentence the caregiver can act on
    severity: Literal["fix", "note"]  # fix: hold it for the caregiver; note: worth knowing, not a reason to hold


class PackReview(BaseModel):
    """The verifier (Muse Wonder): the whole pack read against the research, before the caregiver approves it."""

    faithful: bool  # every fact, date and name matches the research and the source
    right_for_reader: bool  # language, reading level, length and tone suit this person
    safe: bool  # no medical advice; no request for money, codes, links or secrecy; a scam is called a scam
    issues: list[ReviewIssue]
    verdict_en: str  # one sentence for the caregiver

    @property
    def approved(self) -> bool:
        return self.faithful and self.safe and not any(i.severity == "fix" for i in self.issues)


class ChildCheck(BaseModel):
    """The child guardian's read of a finished pack for a child; anything it flags is held for the parent."""

    safe_for_child: bool
    concerns_en: list[str]  # what the parent should look at, in plain English; empty if none


class StudioEngagement(BaseModel):
    """One thing the recipient did with a pack, sent back from her phone."""

    format: Format | Literal["pack"]
    # answer_right / answer_missed: a quiz question (value = its index); asked: she sent a relay question (its index)
    event: Literal["opened", "progress", "finished", "answer_right", "answer_missed", "asked", "replied"]
    value: float = Field(0.0, ge=0, le=1000, allow_inf_nan=False)  # progress 0..1, or an index; NaN would break JSON
    text: str = Field("", max_length=2000)
    at: str = ""


class AgentEvent(BaseModel):
    """One line of live agent activity, broadcast to the caregiver's screen while the swarm works."""

    item_id: str
    agent: str  # e.g. "reader", "fact_checker", "maker_note"
    label: str  # plain words, e.g. "Checking the claims on the web"
    state: Literal["working", "done", "failed", "skipped"]
    engine: str = ""
    latency_s: float = 0.0
    detail: str = ""
    extra: dict[str, str] = Field(default_factory=dict)
