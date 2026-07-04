"""Password hashing and session-token helpers."""
from __future__ import annotations

import hashlib
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError

_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except VerifyMismatchError:
        return False
    except Exception:
        return False


def needs_rehash(password_hash: str) -> bool:
    try:
        return _hasher.check_needs_rehash(password_hash)
    except Exception:
        return False


def generate_session_token() -> str:
    """URL-safe opaque token used as the sessions table primary key."""
    return secrets.token_urlsafe(48)


def generate_agent_token() -> str:
    """Opaque bearer token for a server agent, ``fsa_``-prefixed for recognition."""
    return "fsa_" + secrets.token_urlsafe(36)


def hash_agent_token(token: str) -> str:
    """SHA-256 hex digest used to look up an agent token.

    Agent tokens are high-entropy random strings, so a fast digest is safe here
    (argon2 is only needed for low-entropy human passwords). Storing the digest —
    never the plaintext — means a DB leak doesn't expose usable tokens, while the
    deterministic hash still allows a direct indexed lookup.
    """
    return hashlib.sha256(token.encode("utf-8")).hexdigest()
