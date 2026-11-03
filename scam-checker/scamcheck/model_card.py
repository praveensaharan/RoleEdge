"""The Hugging Face model card for the published adapter, filled in with the measured scores."""

from __future__ import annotations

from typing import Any

from .metrics import table
from .policy import SCAM_TYPES, SHORT_SYSTEM

CARD = """\
---
base_model: {base}
library_name: peft
license: apache-2.0
language:
- ja
pipeline_tag: text-generation
tags:
- lora
- scam-detection
- fraud
- phishing
- japanese
---

# {name}

A LoRA adapter for [{base}](https://huggingface.co/{base}) that checks one message received in Japan (SMS, LINE,
WhatsApp, email, a phone call written out, a social-media DM) for scams, and answers with one JSON object:

```json
{{"scam": true, "type": "refund", "red_flags": ["ATMで手続き", "本日中"], "advice": "電話を切って、家族に確認してください。"}}
```

- `type`: {types}, or `none` for a genuine message.
- `red_flags`: phrases copied exactly from the message, so an app can highlight them.
- `advice`: one calm sentence in plain Japanese for an older person.

It is a warning tool, not a guarantee: it can miss new kinds of scam, and it can flag a genuine message. Use it
alongside other checks, and let a person decide.

## Use

```python
from peft import PeftModel
from transformers import AutoModelForImageTextToText, AutoTokenizer

tok = AutoTokenizer.from_pretrained("{base}")
model = AutoModelForImageTextToText.from_pretrained("{base}", dtype="bfloat16", device_map="cuda")
model = PeftModel.from_pretrained(model, "{repo}")

messages = [{{"role": "system", "content": "{short}"}},
            {{"role": "user", "content": "Channel: SMS\\nMessage:\\n【市役所】医療費の還付金があります。本日中にATMで手続きしてください。"}}]
prompt = tok.apply_chat_template(messages, tokenize=False, add_generation_prompt=True, reasoning_strength="low")
prompt += " to=user<|message|>"  # answer straight away, as in training
ids = tok(prompt, return_tensors="pt", add_special_tokens=False).to("cuda")
out = model.generate(**ids, max_new_tokens=256, do_sample=False, eos_token_id=tok.convert_tokens_to_ids("<|eot|>"))
print(tok.decode(out[0, ids["input_ids"].shape[1]:], skip_special_tokens=True))
```

The user message is `Channel: <channel>` (optional), `Sender: <sender>` (optional), then `Message:` and the text.

## Training

- **Data:** Japanese messages written by Muse Spark for every scam type, genuine messages that look like each type
  (real-style city refund notices, police warnings, courier notices), and everyday messages. Code checked that every
  red flag occurs in its message, and a second blind pass had to agree on every label.
- **Method:** LoRA on the language model's attention and MLP layers (the vision encoder is unchanged); the loss is
  only on the answer.

## Results

Catch rate: share of scams caught. False alarms: share of genuine messages flagged. `test` is held-out synthetic
data; `real_test` is real published messages, labelled by their source, never used for training.

{results}
"""


def card(repo: str, base: str, results: dict[str, dict[str, Any]]) -> str:
    return CARD.format(name=repo.split("/")[-1], repo=repo, base=base, short=SHORT_SYSTEM,
                       types=", ".join(f"`{t}`" for t in SCAM_TYPES),
                       results=table(results) if results else "_Scores to be added._")
