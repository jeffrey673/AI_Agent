"""compute_anon_id correctness and runtime-guard tests."""
import pytest

from app.core.anonymization import anon_id_for, compute_anon_id


def test_deterministic_for_same_user():
    a = compute_anon_id(42, salt="x" * 32)
    b = compute_anon_id(42, salt="x" * 32)
    assert a == b


def test_different_users_differ():
    a = compute_anon_id(1, salt="x" * 32)
    b = compute_anon_id(2, salt="x" * 32)
    assert a != b


def test_different_salts_differ():
    a = compute_anon_id(42, salt="a" * 32)
    b = compute_anon_id(42, salt="b" * 32)
    assert a != b


def test_is_16_hex_chars():
    a = compute_anon_id(42, salt="x" * 32)
    assert len(a) == 16
    assert all(c in "0123456789abcdef" for c in a)


def test_empty_salt_raises():
    with pytest.raises(ValueError, match="ANON_SALT"):
        compute_anon_id(42, salt="")


def test_short_salt_raises():
    with pytest.raises(ValueError, match="ANON_SALT"):
        compute_anon_id(42, salt="short")


def test_anon_id_for_reads_settings(monkeypatch):
    # Clear the lru_cache so we re-hit settings
    anon_id_for.cache_clear()
    uid = 123
    direct = compute_anon_id(uid)
    cached = anon_id_for(uid)
    assert direct == cached
