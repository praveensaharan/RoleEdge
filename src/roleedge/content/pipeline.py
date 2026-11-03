"""Content transformer: shared item -> digest -> checker -> saved record.

One strict-JSON model call writes everything the recipient will see; a second call checks it.
Rendering the record into a card, video and calendar file is a separate step (roleedge.render).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

from ..config import OUTPUT_DIR
from ..llm import LLM
from ..models import Digest, DigestRecord, Recipient, VerifyReport
from .ingest import ContentItem
from .prompts import DIGEST_SYSTEM
from .verify import apply_fixes, run_checker, unreadable_dates, unsupported_dates

CONTENT_DIR = OUTPUT_DIR / "content"


def transform(llm: LLM, case_id: str, description: str, item: ContentItem, recipient_key: str,
              recipient: Recipient, today: str) -> DigestRecord:
    system = DIGEST_SYSTEM.format(today=today, **recipient.model_dump())
    messages = [{"role": "system", "content": system}, {"role": "user", "content": item.message_parts()}]
    draft = llm.complete_json(f"digest/{case_id}", messages, Digest, "care_digest")

    fixed = copy.deepcopy(draft.data)
    check = run_checker(llm, case_id, item, fixed, recipient, today)
    issues = apply_fixes(fixed, VerifyReport.model_validate(check.data).issues)
    held = {issue.path for issue in issues if issue.needs_review}  # don't hold the same field twice
    issues += [issue for issue in unreadable_dates(fixed) + unsupported_dates(fixed, item.text, bool(item.images))
               if issue.path not in held]

    return DigestRecord(
        case=case_id, recipient=recipient_key, input=description, media_count=len(item.images),
        digest=Digest.model_validate(fixed), draft_before_verify=Digest.model_validate(draft.data),
        verify_issues=issues, usage=draft.usage.to_dict(), latency_s=draft.latency_s, cached=draft.cached,
        verify_usage=check.usage.to_dict(), verify_latency_s=check.latency_s,
    )


def save(record: DigestRecord, content_dir: Path = CONTENT_DIR) -> Path:
    path = content_dir / record.case / "digest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(record.model_dump(mode="json"), ensure_ascii=False, indent=2), encoding="utf-8")
    return path


def load(case_id: str, content_dir: Path = CONTENT_DIR) -> DigestRecord:
    return DigestRecord.model_validate_json((content_dir / case_id / "digest.json").read_text(encoding="utf-8"))


def summary_line(record: DigestRecord) -> str:
    u, v = record.usage, record.verify_usage
    majors = sum(i.severity == "major" for i in record.verify_issues)
    applied = sum(i.applied for i in record.verify_issues)
    return (f"{record.case:18s} digest {record.latency_s:5.1f}s in {u['input']:5d} out {u['output']:5d} | "
            f"verify {record.verify_latency_s:5.1f}s in {v['input']:5d} out {v['output']:5d} "
            f"issues {len(record.verify_issues)} (major {majors}, "
            f"applied {applied}) | verdict={record.digest.trust.verdict} actions={len(record.digest.actions)} "
            f"replay={record.cached}")
