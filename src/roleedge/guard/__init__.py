"""The tuned child-safety guard: a LoRA fine-tune of Meta's Llama Guard 3 1B on our own child policy.

    policy    the categories, the Llama Guard prompt and answer format (standard library; also runs on Modal)
    data      training data written by Muse Spark and checked by a second blind pass
    metrics   scores on the held-out test set
    client    the app calling the deployed guard

Training, evaluation and serving run on Modal (modal_apps/guard_lora.py); the commands are in docs/GUARD.md.
"""

from .client import TunedGuard, tuned_guard_from_settings
from .policy import CATEGORIES, Verdict, guard_prompt, parse_verdict, target_text

__all__ = ["CATEGORIES", "TunedGuard", "Verdict", "guard_prompt", "parse_verdict", "target_text",
           "tuned_guard_from_settings"]
