"""Tokens of the accounts a family connects (Google, Notion) are stored encrypted, never in plain text, never logged.

The key comes from ``ROLEEDGE_VAULT_KEY``; without one, a key is generated once into ``output/.vault_key`` (readable
by the owner only), which suits a local demo. A deployment sets its own key from a secret store.
"""

from __future__ import annotations

import os
from pathlib import Path

from cryptography.fernet import Fernet, InvalidToken

from ..config import OUTPUT_DIR

KEY_FILE = OUTPUT_DIR / ".vault_key"


class Vault:
    def __init__(self, key: str = "", key_file: Path = KEY_FILE) -> None:
        if not key:
            if not key_file.exists():
                key_file.parent.mkdir(parents=True, exist_ok=True)
                key_file.write_bytes(Fernet.generate_key())
                os.chmod(key_file, 0o600)
            key = key_file.read_text().strip()
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def seal(self, secret: str) -> str:
        return self._fernet.encrypt(secret.encode()).decode()

    def open(self, sealed: str) -> str:
        try:
            return self._fernet.decrypt(sealed.encode()).decode()
        except InvalidToken as exc:
            raise ValueError("This stored token can't be read with the current key; connect the account again.") from exc
