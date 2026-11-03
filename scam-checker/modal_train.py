"""Train, evaluate and publish the scam checker on Modal: a LoRA on Meta's Muse Glimmer 30B (Apache 2.0).

Run from the scam-checker folder, one step at a time (README.md has the details, times and costs):

    modal run modal_train.py::download                      weights into a Modal volume (CPU only, about 60 GB)
    modal run modal_train.py::smoke                         load on an H100, check the prompt format, answer 3 messages
    modal run modal_train.py::train --run v1                LoRA on data/final/train.jsonl
    modal run modal_train.py::evaluate --run base           untrained Glimmer on the test sets
    modal run modal_train.py::evaluate --run v1             the tuned one
    modal run modal_train.py::publish --run v1 --repo you/glimmer-scam-checker-ja    adapter to Hugging Face (private)

The data comes from data/final/ on your machine (made by `python -m scamcheck build`) and is uploaded with each
run. Adapters and logs stay in the Modal volume `scamcheck-runs`; scores are written to results/ on your machine.
Nothing runs on its own, and every GPU function has a time limit.
"""

from __future__ import annotations

import json
import pathlib
import time

import modal

BASE = "meta-models/Muse-Glimmer-30B"
GPU = "H100"  # 80 GB: the 30B model in bf16 is about 60 GB
ROOT = pathlib.Path(__file__).resolve().parent
EOT, DIRECT = "<|eot|>", " to=user<|message|>"  # Glimmer's end of turn; the answer channel (skips the reasoning one)
STRIP = ("<|eot|>", "<|eom|>", "<|end_of_text|>", "<|finetune_right_pad|>")

(ROOT / "data" / "final").mkdir(parents=True, exist_ok=True)  # uploaded with each run; filled by `scamcheck build`
app = modal.App("scamcheck-glimmer")
hf_cache = modal.Volume.from_name("scamcheck-hf-cache", create_if_missing=True)
runs = modal.Volume.from_name("scamcheck-runs", create_if_missing=True)
hf_secret = modal.Secret.from_name("huggingface")  # HF_TOKEN; needs write access only for `publish`
VOLUMES = {"/cache": hf_cache, "/runs": runs}
image = (modal.Image.debian_slim(python_version="3.12")
         .pip_install("torch==2.15.0", "transformers==5.22.1", "peft==0.21.2", "accelerate==1.15.0", "pillow")
         .env({"HF_HOME": "/cache/hf", "TOKENIZERS_PARALLELISM": "false"})
         .add_local_python_source("scamcheck")
         .add_local_dir(ROOT / "data" / "final", "/root/data"))


# ---------------------------------------------------------------- shared helpers (run inside the container)

def _rows(name: str) -> list[dict]:
    path = pathlib.Path("/root/data") / f"{name}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()] if path.exists() else []


def _tokenizer(padding_side: str = "right"):  # noqa: ANN202
    from transformers import AutoTokenizer

    tok = AutoTokenizer.from_pretrained(BASE)
    tok.padding_side = padding_side
    if tok.pad_token_id is None:
        tok.pad_token = "<|finetune_right_pad|>"
    return tok


def _load(run: str | None = None):  # noqa: ANN202
    """Glimmer in bf16 on the GPU, plus the run's adapter (``run="base"`` or None for none)."""
    import torch
    from transformers import AutoModelForImageTextToText

    model = AutoModelForImageTextToText.from_pretrained(BASE, dtype=torch.bfloat16, device_map="cuda")
    if run and run != "base":
        from peft import PeftModel

        model = PeftModel.from_pretrained(model, f"/runs/{run}/adapter")
    return model


def _prompt(tok, row: dict, short: bool, think: bool = False) -> str:  # noqa: ANN001
    """The chat prompt for one row. Unless ``think``, it ends inside the answer channel, so the model answers
    straight away instead of reasoning first (fast, and what the tuned model is trained to do)."""
    from scamcheck.policy import messages

    text = tok.apply_chat_template(messages(row, short), tokenize=False, add_generation_prompt=True,
                                   reasoning_strength="low")
    if tok.bos_token and not text.startswith(tok.bos_token):
        text = tok.bos_token + text
    return text if think else text + DIRECT


def _final(text: str) -> str:
    """The answer-channel message from a generation (after any reasoning), without end tokens."""
    final = text.rsplit("<|message|>", 1)[-1]
    for token in STRIP:
        final = final.split(token, 1)[0]
    return final.strip()


def _generate(model, tok, prompts: list[str], max_new: int, batch: int) -> list[str]:  # noqa: ANN001
    import torch

    order = sorted(range(len(prompts)), key=lambda i: len(prompts[i]))  # similar lengths together: less padding
    texts: dict[int, str] = {}
    for start in range(0, len(order), batch):
        idx = order[start:start + batch]
        enc = tok([prompts[i] for i in idx], return_tensors="pt", padding=True, add_special_tokens=False).to("cuda")
        with torch.no_grad():
            gen = model.generate(**enc, max_new_tokens=max_new, do_sample=False, pad_token_id=tok.pad_token_id,
                                 eos_token_id=tok.convert_tokens_to_ids(EOT))
        for i, seq in zip(idx, gen[:, enc["input_ids"].shape[1]:], strict=True):
            texts[i] = tok.decode(seq, skip_special_tokens=False)
        print(f"  {min(start + batch, len(order))}/{len(order)}", flush=True)
    return [texts[i] for i in range(len(prompts))]


def _lora_targets(model) -> list[str]:  # noqa: ANN001
    """Full names of the language model's linear layers (attention and MLP); the vision encoder is left alone."""
    import torch.nn as nn

    skip = ("vision", "visual", "perception", "projector", "multi_modal", "lm_head", "embed")
    linear = [n for n, m in model.named_modules() if isinstance(m, nn.Linear) and not any(s in n for s in skip)]
    in_lm = [n for n in linear if "language_model" in n]
    return in_lm or linear


# ---------------------------------------------------------------- 1. weights

@app.function(image=image, volumes=VOLUMES, secrets=[hf_secret], timeout=3 * 3600, cpu=4, memory=8192)
def download() -> None:
    """Download Glimmer once into the volume (no GPU), so GPU runs start loading straight away."""
    from huggingface_hub import snapshot_download

    started = time.time()
    path = snapshot_download(BASE)
    hf_cache.commit()
    size = sum(p.stat().st_size for p in pathlib.Path(path).rglob("*") if p.is_file()) / 1e9
    print(f"{BASE}: {size:.1f} GB in {time.time() - started:.0f} s at {path}")


# ---------------------------------------------------------------- 2. smoke test

@app.function(image=image, gpu=GPU, volumes=VOLUMES, secrets=[hf_secret], timeout=45 * 60)
def smoke() -> None:
    """Loads Glimmer, checks the prompt format the training relies on, and answers three messages."""
    import re
    from collections import Counter

    import torch
    from scamcheck.policy import messages, target

    started = time.time()
    tok = _tokenizer("left")
    model = _load()
    print(f"loaded in {time.time() - started:.0f} s; {sum(p.numel() for p in model.parameters()) / 1e9:.1f}B params; "
          f"GPU memory {torch.cuda.memory_allocated() / 1e9:.1f} GB")
    patterns = Counter(re.sub(r"\.\d+\.", ".N.", n) for n, m in model.named_modules() if isinstance(m, torch.nn.Linear))
    print("linear layers:", *(f"{n} x{c}" for n, c in patterns.most_common(25)), sep="\n  ")
    print(f"LoRA would go on {len(_lora_targets(model))} layers, e.g. {_lora_targets(model)[:3]}")

    row = {"text": "【市役所】医療費の還付金があります。本日中にATMで手続きしてください。", "channel": "phone", "sender": "",
           "scam": True, "type": "refund", "red_flags": ["本日中にATMで手続き"], "advice": "電話を切りましょう。"}
    prompt = _prompt(tok, row, short=True)
    full = tok.apply_chat_template(messages(row, True) + [{"role": "assistant", "content": target(row)}],
                                   tokenize=False, reasoning_strength="low")
    if tok.bos_token and not full.startswith(tok.bos_token):
        full = tok.bos_token + full
    print("--- short prompt as the model sees it ---", prompt, "--- end ---", sep="\n")
    ok = full == prompt + target(row) + EOT
    print(f"training format matches the chat template: {ok}")
    if not ok:
        print("chat template renders the answer as:", repr(full[len(prompt) - len(DIRECT):][:300]))

    tests = [row, {"text": "〇〇市役所です。高額療養費の支給決定通知書を郵送しました。ご指定の口座へ自動で振り込みます。ATMでの手続きは不要です。",
                   "channel": "sms", "sender": ""},
             {"text": "お母さん、今週末そっちに帰るね。お土産なにがいい？", "channel": "line", "sender": "健太"}]
    started = time.time()
    answers = _generate(model, tok, [_prompt(tok, r, short=False) for r in tests], max_new=200, batch=3)
    print(f"3 answers from untrained Glimmer (full prompt, no reasoning) in {time.time() - started:.0f} s:")
    for r, a in zip(tests, answers, strict=True):
        print(f"  {r['text'][:40]}...\n    -> {_final(a)}")


# ---------------------------------------------------------------- 3. training

@app.function(image=image, gpu=GPU, volumes=VOLUMES, secrets=[hf_secret], timeout=6 * 3600)
def train_remote(run: str, epochs: float, lr: float, rank: int, batch: int, accum: int, max_rows: int) -> dict:
    import math
    import random

    import torch
    from peft import LoraConfig, get_peft_model
    from scamcheck.policy import target

    tok = _tokenizer("right")
    rows, val = _rows("train"), _rows("val")
    if max_rows:
        rows = rows[:max_rows]
    if not rows:
        raise SystemExit("No training rows: run `python -m scamcheck build` first.")

    def encode(row: dict) -> tuple[list[int], list[int]]:
        p = tok(_prompt(tok, row, short=True), add_special_tokens=False)["input_ids"]
        c = tok(target(row) + EOT, add_special_tokens=False)["input_ids"]
        return p + c, [-100] * len(p) + c  # the loss is only on the answer

    data, val_data = [encode(r) for r in rows], [encode(r) for r in val[:300]]
    lengths = sorted(len(x) for x, _ in data)
    print(f"{len(data)} training rows, {len(val_data)} val rows; tokens per row: median {lengths[len(lengths) // 2]}, "
          f"max {lengths[-1]}; {sum(lengths):,} tokens per epoch")

    model = _load()
    model.config.use_cache = False
    model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})
    model.enable_input_require_grads()
    targets = _lora_targets(model)
    model = get_peft_model(model, LoraConfig(r=rank, lora_alpha=2 * rank, lora_dropout=0.05, target_modules=targets))
    model.print_trainable_parameters()

    def batches(items: list, shuffle: bool, seed: int) -> list[list]:
        order = sorted(range(len(items)), key=lambda i: len(items[i][0]))
        groups = [order[i:i + batch] for i in range(0, len(order), batch)]
        if shuffle:
            random.Random(seed).shuffle(groups)
        return [[items[i] for i in g] for g in groups]

    def collate(group: list) -> dict:
        width = max(len(x) for x, _ in group)
        ids = [x + [tok.pad_token_id] * (width - len(x)) for x, _ in group]
        labels = [y + [-100] * (width - len(y)) for _, y in group]
        mask = [[1] * len(x) + [0] * (width - len(x)) for x, _ in group]
        return {k: torch.tensor(v, device="cuda") for k, v in (("input_ids", ids), ("labels", labels), ("attention_mask", mask))}

    def val_loss() -> float:
        model.eval()
        total, count = 0.0, 0
        with torch.no_grad():
            for group in batches(val_data, False, 0):
                total += model(**collate(group)).loss.item() * len(group)
                count += len(group)
        model.train()
        return total / max(1, count)

    params = [p for p in model.parameters() if p.requires_grad]
    optimizer = torch.optim.AdamW(params, lr=lr, weight_decay=0.0)
    per_epoch = math.ceil(len(data) / batch / accum)
    total_steps = max(1, round(per_epoch * epochs))
    warmup = max(1, total_steps // 30)
    schedule = torch.optim.lr_scheduler.LambdaLR(optimizer, lambda s: min(1.0, (s + 1) / warmup) * (
        0.1 + 0.9 * 0.5 * (1 + math.cos(math.pi * min(1.0, s / total_steps)))))
    log = {"run": run, "base": BASE, "rows": len(data), "epochs": epochs, "lr": lr, "rank": rank, "batch": batch,
           "accum": accum, "steps": total_steps, "lora_layers": len(targets), "loss": [], "val_loss": []}
    log["val_loss"].append({"step": 0, "loss": round(val_loss(), 4)})
    print(f"val loss before training: {log['val_loss'][0]['loss']}; {total_steps} optimizer steps")

    model.train()
    step, started, running = 0, time.time(), []
    out = pathlib.Path(f"/runs/{run}")
    epoch = 0
    while step < total_steps:
        groups = batches(data, True, epoch)
        for k, group in enumerate(groups):
            loss = model(**collate(group)).loss / accum
            loss.backward()
            running.append(loss.item() * accum)
            if (k + 1) % accum and k + 1 != len(groups):
                continue
            torch.nn.utils.clip_grad_norm_(params, 1.0)
            optimizer.step()
            schedule.step()
            optimizer.zero_grad(set_to_none=True)
            step += 1
            if step % 10 == 0 or step == total_steps:
                mean = sum(running) / len(running)
                running = []
                left = (time.time() - started) / step * (total_steps - step)
                log["loss"].append({"step": step, "loss": round(mean, 4)})
                print(f"step {step}/{total_steps}  loss {mean:.4f}  lr {schedule.get_last_lr()[0]:.2e}  "
                      f"about {left / 60:.0f} min left", flush=True)
            if step % max(1, per_epoch // 2) == 0 or step == total_steps:
                log["val_loss"].append({"step": step, "loss": round(val_loss(), 4)})
                print(f"  val loss {log['val_loss'][-1]['loss']}", flush=True)
            if step >= total_steps:
                break
        epoch += 1
        model.save_pretrained(out / "adapter")
        runs.commit()
    log["minutes"] = round((time.time() - started) / 60, 1)
    (out / "train.json").write_text(json.dumps(log, indent=1))
    runs.commit()
    print(f"saved the adapter to the volume scamcheck-runs at /{run}/adapter after {log['minutes']} min")
    return log


@app.local_entrypoint()
def train(run: str = "v1", epochs: float = 2.0, lr: float = 1e-4, rank: int = 16, batch: int = 4, accum: int = 4,
          max_rows: int = 0) -> None:
    """LoRA training. Try `--max-rows 200 --epochs 1` first: a few minutes, to see the loss fall."""
    log = train_remote.remote(run, epochs, lr, rank, batch, accum, max_rows)
    path = ROOT / "results" / f"train_{run}.json"
    path.parent.mkdir(exist_ok=True)
    path.write_text(json.dumps(log, indent=1))
    print(f"loss curve in {path}")


# ---------------------------------------------------------------- 4. evaluation

@app.function(image=image, gpu=GPU, volumes=VOLUMES, secrets=[hf_secret], timeout=3 * 3600)
def evaluate_remote(run: str, limit: int, think: bool, batch: int) -> dict:
    tok = _tokenizer("left")
    model = _load(run)
    model.eval()
    short = run != "base"  # the tuned model learned the rules; the untrained one gets the full prompt
    out = {}
    for name in ("test", "real_test"):
        rows = _rows(name)[:limit or None]
        if not rows:
            continue
        started = time.time()
        print(f"{name}: {len(rows)} messages")
        raws = _generate(model, tok, [_prompt(tok, r, short, think) for r in rows], 1024 if think else 256, batch)
        print(f"  {time.time() - started:.0f} s")
        out[name] = {"rows": rows, "answers": [_final(r) for r in raws], "raw": raws}
    return out


@app.local_entrypoint()
def evaluate(run: str = "base", limit: int = 0, think: bool = False, batch: int = 16) -> None:
    """Answers every test message and scores them here; `--think` lets the untrained model reason first (slower)."""
    from scamcheck.metrics import save, table

    out = evaluate_remote.remote(run, limit, think, batch)
    name = f"Glimmer {run}" + (" (thinking)" if think else "")
    path = ROOT / "results" / f"glimmer_{run}{'_think' if think else ''}.json"
    scores = save(path, name, {k: (v["rows"], v["answers"]) for k, v in out.items()})
    print(table({name: scores}))
    print(f"every prediction is in {path}")


# ---------------------------------------------------------------- 5. publishing

@app.function(image=image, volumes=VOLUMES, secrets=[hf_secret], timeout=30 * 60)
def publish_remote(run: str, repo: str, private: bool, card: str) -> str:
    from huggingface_hub import HfApi

    api = HfApi()
    api.create_repo(repo, private=private, exist_ok=True)
    folder = pathlib.Path(f"/runs/{run}/adapter")
    (folder / "README.md").write_text(card, encoding="utf-8")
    api.upload_folder(repo_id=repo, folder_path=str(folder), commit_message=f"scam checker LoRA, run {run}")
    return f"https://huggingface.co/{repo}"


@app.local_entrypoint()
def publish(run: str = "v1", repo: str = "", public: bool = False) -> None:
    """Uploads the adapter with a model card (private unless --public). Needs a write token in the secret."""
    if not repo:
        raise SystemExit("Give --repo your-name/glimmer-scam-checker-ja")
    from scamcheck.model_card import card

    results = {}
    for path in sorted((ROOT / "results").glob("*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if "scores" in data:
            results[data["model"]] = data["scores"]
    print(publish_remote.remote(run, repo, not public, card(repo, BASE, results)))
