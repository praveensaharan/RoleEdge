"""The final send gate holds what scams need, and verified mail must really be verified (PIVOT.md T5, T8)."""

import pytest

from roleedge.gates import check_outgoing, check_sender


@pytest.mark.parametrize("text, rule", [
    ("Mom, please send money to this bank account today", "money"),
    ("Can you go to the ATM for me?", "money"),
    ("お母さん、至急お金を振り込んで", "money"),
    ("Tell me the verification code you just got", "code"),
    ("暗証番号を教えて", "code"),
    ("My card is 4111 1111 1111 1111", "card"),
    ("Open www.example-prize.xyz to claim it", "link"),
    ("Look at https://bit.ly/abc", "link"),
    ("Don't tell anyone about this", "secrecy"),
    ("これは内緒にしてね", "secrecy"),
])
def test_hard_rules_hold_and_cannot_be_overridden(text, rule):
    for allow_soft in (False, True):
        result = check_outgoing(text, allow_soft=allow_soft)
        assert not result.passed
        assert rule in result.rules


def test_soft_rules_hold_until_the_caregiver_overrides():
    held = check_outgoing("Please call 090-1234-5678 right now")
    assert not held.passed and set(held.rules) == {"phone", "pressure"}
    assert check_outgoing("Please call 090-1234-5678 right now", allow_soft=True).passed


def test_ordinary_family_messages_pass():
    for text in ("What are you cooking tonight?", "今夜は何を作るの？", "I'll call you after my meeting, around 3.",
                 "If you feel unwell, call 119.", "Onions are on their way. They cost about 198 yen."):
        assert check_outgoing(text).passed, text


def test_full_width_text_is_normalised_before_checking():
    assert not check_outgoing("ｈｔｔｐｓ://example.com").passed


def test_verified_courier_mail_is_usable():
    verdict = check_sender("Yamato <info@kuronekoyamato.co.jp>", "mx.example; dkim=pass; spf=pass; dmarc=pass")
    assert verdict.usable


def test_spoofed_courier_mail_is_not_usable():
    verdict = check_sender("Sagawa <no-reply@sagawa-exp.co.jp>", "mx.example; spf=fail; dkim=none; dmarc=fail")
    assert not verdict.usable and "failed sender authentication" in verdict.reason


def test_lookalike_domain_is_not_on_the_list():
    assert not check_sender("notice@sagawa-exp.co.jp.delivery-check.top", "dmarc=pass").usable


def test_the_caregivers_own_mail_is_usable():
    assert check_sender("Kenji <kenji@example.com>", "", owner_address="kenji@example.com").usable
