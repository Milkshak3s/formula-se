from datetime import datetime, timedelta, timezone

from app.core.security import generate_agent_token, hash_agent_token
from app.services.servers import (
    absolutize_url,
    is_online,
    normalize_reported_state,
)


def test_agent_token_format_and_uniqueness():
    a = generate_agent_token()
    b = generate_agent_token()
    assert a.startswith("fsa_") and b.startswith("fsa_")
    assert a != b  # secrets-backed, not a fixed value


def test_hash_agent_token_is_deterministic_and_hex():
    tok = generate_agent_token()
    digest = hash_agent_token(tok)
    assert digest == hash_agent_token(tok)  # deterministic → indexable lookup
    assert len(digest) == 64 and int(digest, 16) >= 0  # sha256 hex
    assert hash_agent_token(tok + "x") != digest  # different token → different hash


def test_is_online_around_timeout():
    now = datetime(2026, 7, 4, 12, 0, 0, tzinfo=timezone.utc)
    assert is_online(now - timedelta(seconds=5), now=now) is True
    assert is_online(now - timedelta(seconds=45), now=now) is False
    assert is_online(None, now=now) is False
    # naive timestamps (as some drivers hand back) are treated as UTC.
    assert is_online((now - timedelta(seconds=5)).replace(tzinfo=None), now=now) is True


def test_absolutize_url():
    base = "https://fse.mlk.sh/"
    assert (
        absolutize_url("/api/files/prepared-worlds/x.zip", base)
        == "https://fse.mlk.sh/api/files/prepared-worlds/x.zip"
    )
    # already-absolute (B2 presigned) URLs pass through untouched.
    abs_url = "https://s3.us-east-005.backblazeb2.com/formula-se/x.zip?sig=abc"
    assert absolutize_url(abs_url, base) == abs_url


def test_normalize_reported_state():
    assert normalize_reported_state("running") == "running"
    assert normalize_reported_state("STARTING") == "starting"
    assert normalize_reported_state("bogus") == "idle"
    assert normalize_reported_state(None) == "idle"
