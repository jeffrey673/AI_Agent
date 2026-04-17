"""Pseudonymization helper for conversation / feedback ownership.

``anon_id = hmac_sha256(salt, str(user_id))[:16]`` — deterministic per-user so
the sidebar still groups a user's own conversations, yet irreversible without
the server-side salt.

The salt comes from ``Settings.anon_salt`` (env var ``ANON_SALT``). Minimum
32 chars is enforced here, not at config load, so the server boots in dev
without forcing a secret to be set — the guard fires the first time identity
actually needs to be hashed.
"""
from __future__ import annotations

import hashlib
import hmac
from functools import lru_cache

from app.config import get_settings

_MIN_SALT_LEN = 32
_ANON_ID_LEN = 16


def compute_anon_id(user_id: int, *, salt: str | None = None) -> str:
    """Return a 16-char hex anon id for ``user_id``.

    Raises ValueError if ``salt`` (or ``Settings.anon_salt``) is shorter than
    32 chars — this is a hard stop, not a warning: a missing salt would
    collapse every user to a predictable hash.
    """
    if salt is None:
        salt = get_settings().anon_salt
    if not salt or len(salt) < _MIN_SALT_LEN:
        raise ValueError(
            f"ANON_SALT must be set and >= {_MIN_SALT_LEN} chars "
            "(generate with: python -c \"import secrets; print(secrets.token_hex(32))\")"
        )
    mac = hmac.new(salt.encode("utf-8"), str(user_id).encode("utf-8"), hashlib.sha256)
    return mac.hexdigest()[:_ANON_ID_LEN]


@lru_cache(maxsize=1024)
def anon_id_for(user_id: int) -> str:
    """Cached variant keyed on user_id. Safe because the salt is process-stable."""
    return compute_anon_id(user_id)
