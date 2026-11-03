"""Fixed words the parent's phone shows that no model writes (alerts, acknowledgements), per language."""

from __future__ import annotations

PARENT_TEXT: dict[str, dict[str, str]] = {
    "en": {
        "ack_title": "Message received",
        "alert_title": "{caregiver} has been told",
        "alert_spoken": "{caregiver} has been told right away. If you need help now, call {number}.",
        "alert_button": "Call {number}",
    },
    "ja": {
        "ack_title": "伝えました",
        "alert_title": "{caregiver}さんに知らせました",
        "alert_spoken": "{caregiver}さんにすぐ知らせました。今すぐ助けが必要なら、{number}に電話してください。",
        "alert_button": "{number}に電話",
    },
}

CAREGIVER_ALERT = "{parent} said something urgent: “{quote}”. Call her now."
