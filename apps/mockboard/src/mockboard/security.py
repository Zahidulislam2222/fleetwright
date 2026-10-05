"""Small security helpers for the board: password hashing, tokens, OTP codes."""

from __future__ import annotations

import hashlib
import hmac
import secrets

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

_hasher = PasswordHasher()
# Hash of a random password, verified against when the username is unknown, so a wrong username
# costs the same time as a wrong password (no account enumeration by timing).
_DUMMY_HASH = _hasher.hash(secrets.token_urlsafe(16))


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(stored_hash: str | None, password: str) -> bool:
    try:
        return _hasher.verify(stored_hash or _DUMMY_HASH, password) and stored_hash is not None
    except (VerificationError, InvalidHashError):
        return False


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def new_otp(length: int) -> str:
    return "".join(str(secrets.randbelow(10)) for _ in range(length))


def otp_hash(challenge_token: str, code: str) -> str:
    return hmac.new(challenge_token.encode(), code.encode(), hashlib.sha256).hexdigest()


def same(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode(), b.encode())


_rng = secrets.SystemRandom()


def chance(p: float) -> bool:
    return p > 0 and _rng.random() < p


def uniform(lo: float, hi: float) -> float:
    return _rng.uniform(lo, hi)


def randint(lo: int, hi: int) -> int:
    return _rng.randint(lo, hi)


def choice[T](items: list[T]) -> T:
    return _rng.choice(items)
