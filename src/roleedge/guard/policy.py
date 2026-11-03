"""The child-safety policy the tuned guard learns, and its prompt and answer format.

Standard library only: this same file is copied into the Modal image (training, evaluation, serving) and used by
the app, so the prompt the guard was trained on is exactly the prompt it is asked with.

The format is Llama Guard 3's, so the base model already understands it: the categories are listed in the prompt
as S1..S6, the line to check is the "Agent" message, and the answer is ``safe``, or ``unsafe`` with a second line
naming the categories it breaks (``unsafe\\nS4,S5``). The categories are ours (what a parent would not want in a
pack for a young child), not Llama Guard's default hazard list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

CATEGORIES: dict[str, tuple[str, str]] = {
    "S1": ("Frightening or violent",
           "Violence, injury, death, disasters, monsters or threats described in a way that would scare a child."),
    "S2": ("Sexual content or dating",
           "Sexual content, nudity, kissing or romance, crushes or dating."),
    "S3": ("Alcohol, drugs or gambling",
           "Alcohol, smoking, vaping, drugs, gambling or betting presented as normal, fun or worth trying."),
    "S4": ("Money, buying or sign-ups",
           "Asking the child to buy, pay, subscribe, sign up, download an app, enter a contest or click a link."),
    "S5": ("Personal information, secrets or contact",
           "Asking for a name, school, address, phone number, photos or passwords; keeping secrets from parents; "
           "contacting, following or meeting someone."),
    "S6": ("Medical advice",
           "Diagnosis, medicines or doses, or telling a child what to take or do about a health problem instead "
           "of going to a parent or doctor."),
}
LANGUAGE_NAMES = {"en": "English", "ja": "Japanese"}
_CODE = re.compile(r"\bS\d{1,2}\b")


@dataclass(frozen=True)
class Verdict:
    safe: bool
    categories: list[str] = field(default_factory=list)  # codes from CATEGORIES, empty when safe
    parsed: bool = True  # False when the model's answer was not in the format (treated as not safe)

    @property
    def names(self) -> list[str]:
        return [CATEGORIES[c][0] for c in self.categories if c in CATEGORIES]


def guard_prompt(line: str, age: int | None = None, language: str = "") -> str:
    """The full Llama Guard 3 prompt (special tokens included) asking about one line meant for a child."""
    who = f"a child aged {age}" if age else "a child"
    lang = f", in {LANGUAGE_NAMES.get(language, language)}" if language else ""
    categories = "\n".join(f"{code}: {name}.\n{rule}" for code, (name, rule) in CATEGORIES.items())
    return ("<|begin_of_text|><|start_header_id|>user<|end_header_id|>\n\n"
            "Task: Check if there is unsafe content in 'Agent' messages in conversations according to our safety "
            "policy with the below categories.\n\n"
            f"<BEGIN UNSAFE CONTENT CATEGORIES>\n{categories}\n<END UNSAFE CONTENT CATEGORIES>\n\n"
            "<BEGIN CONVERSATION>\n\n"
            f"User: A parent asked for something to be explained to {who}{lang}.\n\n"
            f"Agent: {' '.join(line.split())}\n\n"
            "<END CONVERSATION>\n\n"
            "Provide your safety assessment for ONLY THE LAST Agent message in the above conversation:\n"
            " - First line must read 'safe' or 'unsafe'.\n"
            " - If unsafe, a second line must include a comma-separated list of violated categories."
            "<|eot_id|><|start_header_id|>assistant<|end_header_id|>\n\n")


def target_text(safe: bool, categories: list[str]) -> str:
    """What the guard should answer (the training target), ending with Llama 3's end-of-turn token."""
    codes = [c for c in CATEGORIES if c in categories]
    if not safe and not codes:
        raise ValueError("an unsafe example needs at least one category")
    return ("safe" if safe else f"unsafe\n{','.join(codes)}") + "<|eot_id|>"


def parse_verdict(answer: str) -> Verdict:
    """Read the guard's answer. Anything not in the format counts as not safe, so a confused guard holds the pack
    for the parent instead of letting it through."""
    lines = [line.strip() for line in answer.replace("<|eot_id|>", "").strip().splitlines() if line.strip()]
    first = lines[0].lower() if lines else ""
    if first == "safe":
        return Verdict(safe=True)
    if first == "unsafe":
        codes = [c for c in _CODE.findall(" ".join(lines[1:])) if c in CATEGORIES]
        return Verdict(safe=False, categories=sorted(set(codes), key=list(CATEGORIES).index))
    return Verdict(safe=False, parsed=False)
