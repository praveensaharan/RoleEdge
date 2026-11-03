"""Verified company mail (PIVOT.md T8): mail from a company counts only if it is authenticated and allow-listed.

Fake delivery notices that pretend to come from couriers are one of the most common scams in Japan, so a courier
mail that fails sender authentication must never reach the parent as "your parcel comes Monday". The check reads
the ``Authentication-Results`` header that the receiving mail server adds (SPF, DKIM and DMARC results).

Only facts are taken from a verified company mail, never links or instructions (the send gate enforces that).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Companies whose verified mail may be used for facts like delivery dates. Synthetic demo inboxes use these too.
ALLOWED_SENDER_DOMAINS = frozenset({
    "kuronekoyamato.co.jp", "sagawa-exp.co.jp", "post.japanpost.jp", "japanpost.jp",
    "amazon.co.jp", "rakuten.co.jp", "ups.com", "fedex.com", "dhl.com",
    "uber.com", "amazon.com", "instacart.com", "usps.com",
})


@dataclass(frozen=True)
class MailVerdict:
    usable: bool
    reason: str  # plain words for the activity log
    domain: str


def check_sender(from_address: str, authentication_results: str, *, owner_address: str = "",
                 allowed_domains: frozenset[str] = ALLOWED_SENDER_DOMAINS) -> MailVerdict:
    """Mail the caregiver wrote is always usable; other mail only if allow-listed and DMARC (or SPF and DKIM)
    pass for that domain."""
    address = _address(from_address)
    domain = address.rsplit("@", 1)[-1] if "@" in address else ""
    if owner_address and address == _address(owner_address):
        return MailVerdict(True, "written by you", domain)
    if not _allowed(domain, allowed_domains):
        return MailVerdict(False, f"{domain or 'unknown sender'} is not on the list of verified companies", domain)
    results = authentication_results.lower()
    dmarc = re.search(r"dmarc=(\w+)", results)
    spf = re.search(r"spf=(\w+)", results)
    dkim = re.search(r"dkim=(\w+)", results)
    passed = (dmarc and dmarc.group(1) == "pass") or (
        spf and spf.group(1) == "pass" and dkim and dkim.group(1) == "pass")
    if not passed:
        return MailVerdict(False, f"claims to be from {domain} but failed sender authentication", domain)
    return MailVerdict(True, f"verified mail from {domain}", domain)


def _address(header: str) -> str:
    match = re.search(r"<([^>]+)>", header)
    return (match.group(1) if match else header).strip().lower()


def _allowed(domain: str, allowed: frozenset[str]) -> bool:
    return any(domain == d or domain.endswith("." + d) for d in allowed)
