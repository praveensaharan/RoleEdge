"""The tuned child guard on Modal: LoRA on Meta's Llama Guard 3 1B, trained on our child policy (English and
Japanese), evaluated against the base model, and served as an endpoint that scales to zero.

Nothing runs by itself; each step is one command (docs/GUARD.md), through the project's Modal sign-in:

    python -m roleedge.guard_cli modal run modal_apps/guard_lora.py::train --run v1
    python -m roleedge.guard_cli modal run modal_apps/guard_lora.py::evaluate --run base
    python -m roleedge.guard_cli modal run modal_apps/guard_lora.py::evaluate --run v1
    python -m roleedge.guard_cli modal deploy modal_apps/guard_lora.py
    python -m roleedge.guard_cli modal app stop roleedge-child-guard

The prompt and answer format come from src/roleedge/guard/policy.py, copied into the image, so training,
evaluation, serving and the app all use the same text. Llama Guard is a Meta model, so the guard keeps the
"strict" rule (every model called at runtime is a Meta model).
"""

from __future__ import annotations

import hmac
import json
import os
import pathlib

import modal
from fastapi import Header, HTTPException

BASE_MODEL = "meta-llama/Llama-Guard-3-1B"  # gated: accept Meta's licence on Hugging Face first
GPU = "L4"  # 24 GB; plenty for a 1B model in bf16 with LoRA
MAX_LINES, MAX_CHARS = 64, 1000

ROOT = pathlib.Path(__file__).resolve().parents[1]
POLICY = ROOT / "src" / "roleedge" / "guard" / "policy.py"
DATA = ROOT / "output" / "guard" / "data"

app = modal.App("roleedge-child-guard")
hf_cache = modal.Volume.from_name("roleedge-hf-cache", create_if_missing=True)  # shared with the other Modal apps
runs = modal.Volume.from_name("roleedge-guard-runs", create_if_missing=True)  # adapters, training logs, serving.txt
hf_secret = modal.Secret.from_name("huggingface")  # HF_TOKEN
key_secret = modal.Secret.from_name("roleedge-guard")  # GUARD_KEY, the same value as ROLEEDGE_GUARD_KEY in .env
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.6.0", "transformers==4.51.3", "peft==0.15.2", "accelerate==1.6.0",
                      "fastapi[standard]==0.115.12")
         .env({"HF_HOME": "/cache/hf", "TOKENIZERS_PARALLELISM": "false"})
         .add_local_file(POLICY, "/root/guard_policy.py"))
volumes = {"/cache": hf_cache, "/runs": runs}


def check_request(body: object, authorization: str, key: str) -> tuple[list[str], int | None, str]:
    """The endpoint's door: the shared key, then at most MAX_LINES lines of text, each cut to MAX_CHARS."""
    if not key or not hmac.compare_digest(authorization.encode(), f"Bearer {key}".encode()):
        raise HTTPException(401, "A valid guard key is required.")
    lines = body.get("lines") if isinstance(body, dict) else None
    if not isinstance(lines, list) or not 0 < len(lines) <= MAX_LINES or not all(isinstance(x, str) for x in lines):
        raise HTTPException(422, f"Send 1 to {MAX_LINES} lines of text.")
    age = body.get("age")
    language = str(body.get("language") or "")[:5]
    return [line[:MAX_CHARS] for line in lines], age if isinstance(age, int) and not isinstance(age, bool) else None, language


def _policy():  # noqa: ANN202
    import sys

    sys.path.insert(0, "/root")
    import guard_policy

    return guard_policy


def _tokenizer(padding_side: str):  # noqa: ANN202
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(BASE_MODEL, token=os.environ.get("HF_TOKEN"))
    tok.pad_token = tok.pad_token or tok.eos_token  # Llama has no pad token
    tok.padding_side = padding_side
    return tok


def _load(run: str):  # noqa: ANN202
    """The base model, plus the run's adapter merged in (``run="base"`` for none), ready to generate."""
    import torch
    from transformers import AutoModelForCausalLM

    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.bfloat16, device_map="cuda",
                                                 token=os.environ.get("HF_TOKEN"))
    hf_cache.commit()
    if run != "base":
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, f"/runs/{run}/adapter").merge_and_unload()
    model.eval()
    return model, _tokenizer("left")


def _generate(model, tok, prompts: list[str], batch: int = 16) -> list[str]:  # noqa: ANN001
    import torch

    answers: list[str] = []
    for start in range(0, len(prompts), batch):
        enc = tok(prompts[start:start + batch], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        with torch.no_grad():
            out = model.generate(**enc, max_new_tokens=12, do_sample=False, pad_token_id=tok.pad_token_id)
        answers += tok.batch_decode(out[:, enc["input_ids"].shape[1]:], skip_special_tokens=True)
    return answers


# ---------------------------------------------------------------- training

@app.function(gpu=GPU, image=image, volumes=volumes, secrets=[hf_secret], timeout=2 * 60 * 60)
def train_lora(train_rows: list[dict], val_rows: list[dict], run: str, epochs: float = 3.0, lr: float = 2e-4,
               rank: int = 16) -> dict:
    """Supervised LoRA: the loss is only on the answer ("safe" / "unsafe\\nS4"), never on the prompt."""
    import torch
    from peft import LoraConfig, get_peft_model
    from transformers import AutoModelForCausalLM, DataCollatorForSeq2Seq, Trainer, TrainingArguments

    policy, tok = _policy(), _tokenizer("right")
    model = AutoModelForCausalLM.from_pretrained(BASE_MODEL, torch_dtype=torch.bfloat16,
                                                 token=os.environ.get("HF_TOKEN")).to("cuda")
    hf_cache.commit()
    model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.05, task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj",
                                                             "up_proj", "down_proj"]))

    def encode(row: dict) -> dict:
        prompt = tok(policy.guard_prompt(row["text"], row.get("age"), row.get("lang", "")), add_special_tokens=False)["input_ids"]
        answer = tok(policy.target_text(row["safe"], row["categories"]), add_special_tokens=False)["input_ids"]
        return {"input_ids": prompt + answer, "attention_mask": [1] * (len(prompt) + len(answer)),
                "labels": [-100] * len(prompt) + answer}

    args = TrainingArguments(output_dir=f"/runs/{run}/work", num_train_epochs=epochs, learning_rate=lr,
                             per_device_train_batch_size=8, per_device_eval_batch_size=8, gradient_accumulation_steps=2,
                             lr_scheduler_type="cosine", warmup_ratio=0.05, bf16=True, logging_steps=10,
                             eval_strategy="epoch", save_strategy="no", report_to=[], remove_unused_columns=False, seed=7)
    trainer = Trainer(model=model, args=args, train_dataset=[encode(r) for r in train_rows],
                      eval_dataset=[encode(r) for r in val_rows],
                      data_collator=DataCollatorForSeq2Seq(tok, padding=True, label_pad_token_id=-100))
    result = trainer.train()
    model.save_pretrained(f"/runs/{run}/adapter")
    summary = {"run": run, "base_model": BASE_MODEL, "gpu": GPU, "train_rows": len(train_rows), "val_rows": len(val_rows),
               "epochs": epochs, "lr": lr, "rank": rank, "train_loss": result.training_loss,
               "train_seconds": result.metrics.get("train_runtime"), "eval": trainer.evaluate(),
               "log": trainer.state.log_history}
    pathlib.Path(f"/runs/{run}/train.json").write_text(json.dumps(summary, indent=1))
    pathlib.Path("/runs/serving.txt").write_text(run)  # the endpoint serves the latest trained run
    runs.commit()
    return summary


# ---------------------------------------------------------------- evaluation

@app.function(gpu=GPU, image=image, volumes=volumes, secrets=[hf_secret], timeout=60 * 60)
def predict(rows: list[dict], run: str) -> list[str]:
    """The guard's raw answer for every row (``run="base"`` = Llama Guard 3 1B with our categories, no LoRA)."""
    policy = _policy()
    model, tok = _load(run)
    return _generate(model, tok, [policy.guard_prompt(r["text"], r.get("age"), r.get("lang", "")) for r in rows])


# ---------------------------------------------------------------- serving

@app.cls(gpu=GPU, image=image, volumes=volumes, secrets=[hf_secret, key_secret], scaledown_window=120,
         max_containers=1, timeout=10 * 60)
class Guard:
    """POST {"lines": [...], "age": 8, "language": "ja"} with "Authorization: Bearer <GUARD_KEY>"
    -> {"results": [{"safe": bool, "categories": ["S4"], "parsed": bool}], "model": "..."}."""

    @modal.enter()
    def load(self) -> None:
        serving = pathlib.Path("/runs/serving.txt")
        self.run = serving.read_text().strip() if serving.exists() else "base"
        self.policy = _policy()
        self.model, self.tok = _load(self.run)

    @modal.fastapi_endpoint(method="POST", docs=False)
    def classify(self, body: dict, authorization: str = Header(default="")) -> dict:
        lines, age, language = check_request(body, authorization, os.environ.get("GUARD_KEY", ""))
        prompts = [self.policy.guard_prompt(line, age, language) for line in lines]
        verdicts = [self.policy.parse_verdict(answer) for answer in _generate(self.model, self.tok, prompts)]
        return {"model": f"{BASE_MODEL}+lora:{self.run}" if self.run != "base" else BASE_MODEL,
                "results": [{"safe": v.safe, "categories": v.categories, "parsed": v.parsed} for v in verdicts]}


# ---------------------------------------------------------------- the commands (run on your machine)

@app.local_entrypoint()
def train(run: str = "v1", epochs: float = 3.0, lr: float = 2e-4, rank: int = 16) -> None:
    from roleedge.guard.data import load_jsonl

    train_rows, val_rows = load_jsonl(DATA / "train.jsonl"), load_jsonl(DATA / "val.jsonl")
    print(f"Training '{run}' on {len(train_rows)} lines ({len(val_rows)} for validation), {GPU}, {epochs} epochs...")
    summary = train_lora.remote(train_rows, val_rows, run, epochs, lr, rank)
    out = ROOT / "output" / "guard" / "runs" / run / "train.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1))
    print(f"train loss {summary['train_loss']:.4f}, eval loss {summary['eval'].get('eval_loss', float('nan')):.4f}, "
          f"{summary['train_seconds'] or 0:.0f}s of training -> {out}")


@app.local_entrypoint()
def evaluate(run: str = "v1") -> None:
    from roleedge.guard import parse_verdict
    from roleedge.guard.metrics import save_eval, table
    from roleedge.guard_cli import EVAL_DIR, test_rows

    rows = test_rows()
    print(f"Evaluating '{run}' on {len(rows)} held-out lines ({GPU})...")
    answers = predict.remote(rows, run)
    name = "Llama Guard 3 1B, base (our categories)" if run == "base" else f"Llama Guard 3 1B + LoRA ({run})"
    model = BASE_MODEL if run == "base" else f"{BASE_MODEL}+lora:{run}"
    scores = save_eval(EVAL_DIR / f"{run}.json", name, model, rows, [parse_verdict(a) for a in answers], answers)
    print(table({name: scores}))
