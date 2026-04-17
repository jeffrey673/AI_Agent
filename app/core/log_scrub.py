"""structlog processor that strips identity from log events.

Every emitted log event passes through ``scrub_identity_processor`` before it
hits the renderer. The processor:

- Replaces ``user_id`` with ``anon_id`` (via ``compute_anon_id``)
- Drops ``email``, ``name``, ``display_name`` from the event dict
- Leaves ``audit`` / ``security`` loggers untouched so incident response
  still has real attribution

If ``user_id`` is not int-coercible, it's dropped silently rather than crashing
the log call.
"""
from __future__ import annotations

from typing import Any

from app.core.anonymization import compute_anon_id

_IDENTITY_FIELDS_TO_DROP = ("email", "name", "display_name")
_AUDIT_LOGGERS = {"audit", "security"}


def scrub_identity_processor(
    logger: Any,
    method_name: str,
    event_dict: dict,
    *,
    _logger_name: str | None = None,
) -> dict:
    """Return the event dict with identity fields replaced by anon_id.

    ``_logger_name`` is a test-only hook; in production the caller pulls it
    from the bound logger via ``event_dict.get("logger")`` which structlog
    injects via ``add_logger_name``.
    """
    name = _logger_name if _logger_name is not None else event_dict.get("logger", "")
    if any(name.startswith(ns) for ns in _AUDIT_LOGGERS):
        return event_dict

    uid = event_dict.pop("user_id", None)
    if uid is not None:
        try:
            event_dict["anon_id"] = compute_anon_id(int(uid))
        except (TypeError, ValueError):
            # Not int-coercible or salt missing — drop silently; never emit a
            # partially-identifying value.
            pass

    for k in _IDENTITY_FIELDS_TO_DROP:
        event_dict.pop(k, None)

    return event_dict
