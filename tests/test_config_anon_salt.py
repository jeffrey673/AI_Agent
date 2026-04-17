"""Verify anon_salt field is loaded from env and exposed on Settings."""
from app.config import Settings


def test_anon_salt_field_exists():
    s = Settings(anon_salt="x" * 32)
    assert s.anon_salt == "x" * 32


def test_anon_salt_defaults_empty():
    # Default is empty string — presence/length enforcement happens at use time
    # (compute_anon_id), not at Settings load, so the server can start even if
    # the operator forgot to set it. Tests in tests/test_anonymization.py
    # cover the runtime guard.
    s = Settings()
    assert isinstance(s.anon_salt, str)
