"""structlog processor that replaces user_id with anon_id and drops identity fields."""
from app.core.log_scrub import scrub_identity_processor


def test_scrubs_user_id_to_anon_id():
    event = {"event": "test", "user_id": 42, "email": "a@b.com", "name": "Alice"}
    out = scrub_identity_processor(None, "info", event)
    assert "user_id" not in out
    assert "email" not in out
    assert "name" not in out
    assert "anon_id" in out
    assert len(out["anon_id"]) == 16


def test_drops_display_name_and_email_even_without_user_id():
    event = {"event": "test", "display_name": "Bob", "email": "b@c.com"}
    out = scrub_identity_processor(None, "info", event)
    assert "display_name" not in out
    assert "email" not in out


def test_preserves_audit_logger():
    # Audit-namespace loggers preserve identity for incident response.
    event = {"event": "test", "user_id": 42, "email": "a@b.com"}
    out = scrub_identity_processor(None, "info", event, _logger_name="audit")
    assert out["user_id"] == 42
    assert out["email"] == "a@b.com"


def test_non_numeric_user_id_passes_through_harmlessly():
    # If user_id is not int-coercible, silently drop it rather than crash.
    event = {"event": "test", "user_id": "not-an-int"}
    out = scrub_identity_processor(None, "info", event)
    assert "user_id" not in out
    assert "anon_id" not in out  # couldn't compute, don't emit garbage
