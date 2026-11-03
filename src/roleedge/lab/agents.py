"""The lab's own two specialists: a content profiler (what the reel is and which formats suit it) and a judge (a rubric
score for every moment). Both are evaluation tools; the product's agents are the ones under test."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

from ..models.studio import Format
from ..studio.agents import VERIFIER_MODEL, Specialist

ContentType = Literal["educational", "story_or_steps", "exercise_or_howto", "interesting_idea", "website_or_tool",
                      "entertainment_list", "motivation_or_opinion", "unsuitable_or_too_little"]


class ContentProfile(BaseModel):
    content_type: ContentType
    topic_en: str  # a few words
    has_speech: bool
    has_on_screen_text: bool
    worth_explaining: bool  # is there enough real content to make something useful
    reason_en: str  # one sentence: why this type, and why worth it or not
    best_formats: list[Format]  # most suitable first, from the parent's moments
    risks_en: list[str]  # e.g. "exercise could injure an older person", "financial advice", "unverified health claim"


PROFILER = Specialist("lab/profiler", "Profiling the reel", ContentProfile, effort="low", system="""\
You profile an Instagram reel so the right kind of explanation can be made from it for an older parent (79, reads
English slowly). Use the reel's transcript, on-screen text and the reading of its frames.
content_type: educational (concepts, facts, how something works), story_or_steps (a topic told in order),
exercise_or_howto (physical movements or practical instructions), interesting_idea (one surprising or complex idea),
website_or_tool (it introduces websites, apps or online tools), entertainment_list (movies, shows, songs),
motivation_or_opinion (advice or a personal view), unsuitable_or_too_little (no real content, only music, or not
suitable at all).
best_formats from these ids only, most suitable first (1-3): note (a short note read aloud, warm), steps (slides, one
step or idea per slide), map (a mind map of concepts), askme (a gentle quiz), video (an animated, narrated video,
best for movements and demonstrations), picture (one illustration), card (a page to keep: a list, a date, a place).
Rules of thumb: educational or information-dense -> map; a topic with order -> steps; exercise or how-to -> video;
an interesting idea -> note; websites or tools -> steps (a walkthrough); entertainment lists -> card. risks_en lists
anything unsafe or unsuitable for an older reader (physical risk, money or medical advice, adult content).""")


class Problem(BaseModel):
    problem_en: str
    cause: Literal["prompt", "model", "tool", "workflow", "data"]  # where the fix belongs
    severity: Literal["major", "minor"]


class MomentScore(BaseModel):
    format: str
    faithful: int  # 1-5
    clear: int
    engaging: int
    useful: int
    format_fit: int
    natural: int = 0  # 1-5 from judge v4 on (sounds like the family talking, not a report); 0 = not scored
    covered_points: list[int]  # numbers of the key points this moment carries
    problems: list[Problem]
    verdict_en: str


class Judgement(BaseModel):
    moments: list[MomentScore]
    missing_en: list[str]  # important things none of the moments carry
    best_format: str  # the format that would serve this reel best, from the parent's ids


JUDGE = Specialist("lab/judge", "Judging the moments", Judgement, effort="low", model=VERIFIER_MODEL, system="""\
You are a strict, fair judge of explanations made from Instagram reels for an older parent: Linda, 79, reads English
slowly, prefers short sentences and warmth. You get the reel (title, caption, transcript, a reading of its frames),
its numbered key points, and the moments made from it. Score every moment 1-5 on each criterion, using these anchors:
- faithful: 5 every statement matches the reel and nothing is invented; 3 one small slip or an unsupported claim;
  1 wrong or invented content.
- clear: 5 an older reader gets it at once (short sentences, plain words, one idea at a time); 3 understandable with
  effort; 1 confusing.
- engaging: 5 warm, personal, makes her want to continue; 3 neutral; 1 dull or cold.
- useful: 5 she can remember or do something concrete; 3 vaguely helpful; 1 nothing to take away.
- format_fit: 5 this format is the best way to carry this reel's content; 3 acceptable; 1 the wrong format.
covered_points: the numbers of the key points the moment really carries (not just mentions in passing).
problems: each concrete weakness, its cause (prompt: the agent's instructions; model: the model's ability; tool: a
missing tool such as search or images; workflow: the order or wiring of agents; data: the reel itself lacks it) and
severity. Unsafe advice (exercise an older person could be hurt by, money or medical advice) is always major.
missing_en: important things from the reel that no moment carries. best_format: the parent's moment id (note, steps,
map, askme, video, picture, card) that would serve this reel best. Be specific; do not praise.""")


# Judge v2 (after round 1): the first judge marked right things as faults. It read a note in Maya's voice as an
# invented speaker, scored a picture on its caption alone (it never saw what is drawn), and counted a watch-only
# framing of a risky exercise as missing content. Round 1 was scored again with this judge, so rounds compare like
# for like.
JUDGE_V2 = Specialist("lab/judge_v2", "Judging the moments", Judgement, effort="low", model=VERIFIER_MODEL,
                      system=JUDGE.system + """
How these moments work (do not mark these as faults):
- They are sent by Maya, Linda's daughter, in Maya's own voice ("Mom, ..."). Maya speaking is right, not invented.
- A picture moment is drawn later from picture_to_draw; judge that description with the caption.
- A video scene's shown_picture is a real still from the reel, shown behind the words.
- Exercise that is risky for her at 79 (flips, standing on hands or head, jumps, heavy weights) should be explained as
  something to watch, not to try: that framing is correct and is not missing content. Gentle exercise should keep
  the technique cues and a line to stop if it hurts.
- When the fact check did not confirm the claims, giving them as the speaker's claims ("he says") is correct.""")


# Judge v3 (from round 4): every reel now gets the full set (a lead moment, mind map, slides, quiz, video, picture), so
# format_fit asks whether a moment uses its own format well for this content, not whether another format would be
# better; "steps" are slides. Round 3 was scored again with it, so round 4 compares like for like.
SET_RULE = """
These moments are made together as one set, as the family sees them (a mind map, slides, a quiz, an animated video,
a picture, and a note or card when one leads). format_fit asks whether THIS moment uses its own format well for this
content: a map is a real map of the content's parts, slides ("steps") take one idea per slide in a sensible order, a
quiz checks the content's key facts with fair choices, a video's scenes are worth watching, a picture shows the
subject. It does not ask whether another format would be better. best_format is still the one that serves the reel best."""
JUDGE_V3 = Specialist("lab/judge_v3", "Judging the set", Judgement, effort="low", model=VERIFIER_MODEL,
                      system=JUDGE_V2.system + SET_RULE)

# Judge v4 (round 6): the user's own review of the moments (2026-11-03) asked for a different voice: the family
# talking, not a report about a reel. A sixth score, natural, measures it; round 5 was scored again with judge v4.
NATURAL_RULE = """
Also score natural, 1-5: 5 sounds like Maya really texting her mother, picking up their chat: warm, personal, telling
the content itself as news or a tip ("Nowadays AI is everywhere, and Stanford put its AI class on YouTube for free");
3 correct but stiff or report-like; 1 robotic: she introduces herself ("I am Maya", "This is Maya, I saved this for
you"), narrates the reel ("the reel says", "in this reel", the speaker's coat, the black-and-white picture, the reel's
title), piles up disclaimers ("you do not need to follow or comment", "that promise is not proven", "we do not know
who the speaker is"), or uses labels like "Reel promise", "Check found", "Song words". A scam told as kind news ("there
is a scam going around: they ask for ...") is natural; "this is a scam" is not. A product reel should say what each
product is good for and offer to get it; a video should teach, not describe what the person in the reel does. Links
and product pictures listed as added by the app are checked by code: count them as useful. Count each robotic habit
as a problem with cause prompt."""
JUDGE_V4 = Specialist("lab/judge_v4", "Judging the set", Judgement, effort="low", model=VERIFIER_MODEL,
                      system=JUDGE_V2.system + SET_RULE + NATURAL_RULE)

# The children's judge: the same scores for Leo (9), Maya's son, who gets a picture story, a quiz game, a video, a
# mind map and a picture from the same reel.
JUDGE_CHILD = Specialist("lab/judge_child", "Judging the children's moments", Judgement, effort="low", model=VERIFIER_MODEL,
                         system="""\
You are a strict, fair judge of explanations made from Instagram reels for a child: Leo, 9, Maya's son, reads
English at his age. You get the reel (title, caption, transcript, a reading of its frames), its numbered key points,
the fact check, and the moments made for him. Score every moment 1-5 on each criterion, using these anchors:
- faithful: 5 every statement matches the reel and nothing is invented; 3 one small slip; 1 wrong or invented.
- clear: 5 a 9-year-old gets it at once (short sentences, a concrete example); 3 understandable with help; 1 confusing.
- engaging: 5 fun and playful, makes him want to go on (a story, a game); 3 neutral; 1 dull or preachy.
- useful: 5 he learns or can do something real and safe; 3 vaguely; 1 nothing to take away.
- format_fit: 5 this format is the best way to carry this content for a child; 3 acceptable; 1 the wrong format.
Safety comes first: anything frightening, violent, sexual, about dating, money worries, insults or risky stunts must
be left out or made safe; a moment that keeps it is faithful to the reel but scores 1 on useful and is a major
problem. Leaving unsuitable parts out is correct and is not missing content. The moments are from Maya, his mother.
A picture moment is drawn from picture_to_draw; a video scene's shown_picture is a real still from the reel.
covered_points: the numbers of the key points the moment really carries. problems: each concrete weakness, its
cause (prompt, model, tool, workflow, data) and severity. missing_en: important, child-suitable things no moment
carries. best_format: the child's moment id (story, quiz, video, map, picture, relay). Be specific; do not praise.""" + SET_RULE)
JUDGE_CHILD_V2 = Specialist("lab/judge_child_v2", "Judging the children's set", Judgement, effort="low", model=VERIFIER_MODEL,
                            system=JUDGE_CHILD.system + NATURAL_RULE.replace("Maya really texting her mother", "his mom really talking to Leo")
                            .replace("her mother", "her son"))


# ---------------------------------------------------------------- Notion: find the pages, then answer only from them


class PagePick(BaseModel):
    page_ids: list[str]  # the pages most likely to hold the answer, best first (at most 4); empty if none could
    reason_en: str


NOTION_PICK = Specialist("lab/notion_pick", "Finding the Notion pages", PagePick, effort="low", system="""\
You choose which of a person's Notion pages could answer a question. You get the question and an index: each page's
id, title and the start of its text. Return the ids of the pages that could hold the answer, best first, at most 4.
If the question needs facts from two pages, return both. If no page could hold it, return an empty list.""")


class Citation(BaseModel):
    page_id: str
    quote: str  # copied word for word from that page's text


class NotionAnswer(BaseModel):
    found: bool  # the pages contain the answer
    answer_en: str  # short and plain; if not found, say what is missing and where it might be
    citations: list[Citation]  # every fact in the answer, quoted from the pages
    missing_en: list[str]  # parts of the question the pages don't answer


NOTION_ANSWER = Specialist("lab/notion_answer", "Answering from Notion", NotionAnswer, effort="low", system="""\
You answer a question only from the Notion pages given (each with its id, title and full text). Rules:
- Use only what the pages say. Never fill a gap from general knowledge, and never guess a number, time, name or code.
- Every fact in answer_en has a citation: the page id and a quote copied word for word from that page.
- If you combine pages or do simple arithmetic (days between two dates), cite both facts and show the step briefly.
- If the pages don't contain the answer, set found to false, say plainly that it isn't in the pages, and list what is
  missing in missing_en. A partial answer: found true for what is there, the rest in missing_en.
- Answer about the thing asked, not a near match: if the question names a page or item (a reel, a trip, a list) and
  the pages given are about something else, it isn't found, even if they look related.
- A summary covers the page's main facts (dates, times, places, names, numbers), in short sentences.""")
