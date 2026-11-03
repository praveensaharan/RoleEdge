"""The family relay: a grandchild asks their grandparent something, and the answer comes back to them.

    child's words (typed, or their voice) ──> relay writer ──> send gate ───────────────> grandparent's phone
    grandparent's answer (her voice)      ──> relay writer ──> send gate + child guard ──> child's phone

* The relay writer (model) keeps a child's question in the child's own words for the grandparent. For the child it
  retells the grandparent's answer simply, describes a picture of it and suggests one question to ask next. The
  listener also hears the speaker's own recording when there is one.
* Code checks what reaches each of them: the final send gate (T5) and no date or time that wasn't said (S2); for a
  child, the child-safety review too. Anything held waits for the caregiver, who sees every relay.
* What they say is data, never instructions (T2). If the writer can't run, the words are passed on as they were
  said, and anything for a child is held for the caregiver to read first.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Any

from ..llm import LLM, Message
from ..models import Circle, GateResult, Member, TraceStep
from ..models.relay import RelayMessage
from ..models.studio import AgentEvent, ChildCheck
from .agents import DATA_NOT_INSTRUCTIONS, LANGUAGE_RULES, grandparent_word
from .swarm import Swarm
from .verify import CHILD_RULE, check_pack

WRITER = """\
You pass on what one family member said to another, inside a closed family circle. {speaker} ({speaker_about}) said
something for {listener} ({listener_about}). {task}
Write spoken_text and follow_up in {language}. {language_rule} english_gloss is what {speaker} said, in plain
English, for {caregiver}. Never add facts, dates, times, promises or advice that {speaker} did not say. {data_rule}"""

TO_GRANDPARENT = """\
spoken_text is {speaker}'s words for {listener}, kept as {speaker} said them (only fix what speech recognition
clearly got wrong). picture_en and follow_up are ""."""

TO_CHILD = """\
spoken_text retells {speaker}'s answer for {listener} (age {age}) in 1-3 short, warm sentences, keeping what
{speaker} said, as "{grandparent} says..." would. picture_en is a calm picture-book scene of what {speaker}
described, in English, with no words, logos or real people's faces ("" if there is nothing to picture). follow_up is
one short question {listener} could ask {grandparent} next. If anything {speaker} said is not right for a child of
{age}, leave it out of spoken_text and keep only a gentle version."""

TITLES = {"ja": "{name}から", "en": "From {name}"}
GENERATION = {"parent": "the grandparent", "child": "the grandchild", "caregiver": "the parent"}
PICTURE_STYLE = ("A gentle children's picture-book illustration in soft flat colours, calm and friendly. No text, "
                 "letters, logos or real people's faces. Scene: {scene}")


@dataclass
class Relay:
    message: RelayMessage
    title: str
    gate: GateResult
    guardian: ChildCheck | None = None
    trace: list[TraceStep] = field(default_factory=list)

    def payload(self) -> dict[str, Any]:
        """What the item stores: a ParentMessage-shaped message (so both phones and the approve route read it), and
        what the checks need to run again."""
        return {"message": {"spoken_text": self.message.spoken_text, "screen_title": self.title, "steps": [],
                            "quick_replies": [], "english_gloss": self.message.english_gloss},
                "follow_up": self.message.follow_up, "picture_en": self.message.picture_en,
                "guardian": self.guardian.model_dump() if self.guardian else None}


def name_for(circle: Circle, listener: Member, speaker: Member) -> str:
    """What the listener calls the speaker: a child's word for their grandparent, or the child's name."""
    return grandparent_word(circle, listener) if speaker.role == "parent" else speaker.local_name


def pass_on(llm: LLM, circle: Circle, speaker: Member, listener: Member, said: str, item_id: str,
            emit: Callable[[AgentEvent], None] = lambda event: None) -> Relay:
    """Write the relay for the listener, then run the code checks (and, for a child, the child-safety review)."""
    for_child = listener.role == "child"
    child = listener if for_child else speaker
    values = {"speaker": name_for(circle, listener, speaker), "listener": listener.call_name,
              "speaker_about": f"{GENERATION[speaker.role]}, age {speaker.age}",
              "listener_about": f"{GENERATION[listener.role]}, age {listener.age}", "age": str(listener.age or ""),
              "grandparent": grandparent_word(circle, child), "caregiver": circle.caregiver.call_name,
              "language": listener.language_name, "data_rule": DATA_NOT_INSTRUCTIONS,
              "language_rule": LANGUAGE_RULES[(listener.language, listener.role if for_child else "parent")]
              .format(age=listener.age or "")}
    values["task"] = (TO_CHILD if for_child else TO_GRANDPARENT).format(**values)
    messages: list[Message] = [{"role": "system", "content": WRITER.format(**values)},
                               {"role": "user", "content": f"What {values['speaker']} said:\n{said}"}]
    trace: list[TraceStep] = []
    try:
        result = llm.complete_json("relay/writer", messages, RelayMessage, "relay_writer")
        message = RelayMessage.model_validate(result.data)
        trace.append(TraceStep(step=f"Passed it on for {listener.call_name}", engine=llm.engine,
                               latency_s=result.latency_s, replayed=result.cached))
        written = True
    except Exception as exc:
        message = RelayMessage(spoken_text=said, english_gloss="", picture_en="", follow_up="")
        trace.append(TraceStep(step=f"The relay writer couldn't run ({type(exc).__name__}); passed on as said",
                               engine="code"))
        written = False
    guardian = None
    if for_child:
        if written:
            swarm = Swarm(llm, circle, item_id, emit=emit, recipient=listener)
            guardian = swarm.guard({"relay": {"spoken_text": message.spoken_text, "follow_up": message.follow_up}},
                                   [said, message.picture_en])
            trace.extend(swarm.trace)
        else:
            guardian = ChildCheck(safe_for_child=False, concerns_en=["The relay writer couldn't run. Read it yourself first."])
    title = TITLES.get(listener.language, TITLES["en"]).format(name=values["speaker"])
    relay = Relay(message, title, GateResult(passed=True), guardian, trace)
    relay.gate = check(relay.payload(), said)
    trace.append(TraceStep(step="Final send gate and date check" + (" with the child-safety review" if for_child else "")
                           + ": " + ("passed" if relay.gate.passed else "; ".join(relay.gate.reasons)), engine="code"))
    return relay


def check(payload: dict[str, Any], said: str, allow_soft: bool = False) -> GateResult:
    """The code checks on a relay before the listener sees it, run again when the caregiver approves a held one."""
    message = payload.get("message") or {}
    shown = {"relay": {"spoken_text": message.get("spoken_text", ""), "screen_title": message.get("screen_title", ""),
                       "follow_up": payload.get("follow_up", "")}}
    gate = check_pack(shown, said, allow_soft=allow_soft)
    guardian = payload.get("guardian")
    if guardian and not ChildCheck.model_validate(guardian).safe_for_child and not allow_soft:
        concerns = " ".join(guardian["concerns_en"]) or "Read it yourself before sending."
        return GateResult(passed=False, reasons=[*gate.reasons, f"The child-safety check flagged it: {concerns}"],
                          rules=[*gate.rules, CHILD_RULE])
    return gate
