"""Console sign-in: password (argon2id) then a TOTP code (every account has MFA), with lockout after
repeated failures and one-time use of each TOTP time step. The same answer is returned for an
unknown email and a wrong password, and both take the same time (a dummy hash is verified)."""

from __future__ import annotations

import asyncio
import ipaddress
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID

import pyotp
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from redis.asyncio import Redis
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from fw_core.crypto import Envelope, Sealed, aad_for
from fw_core.db import system_tx, tenant_tx
from fw_core.settings import AuthSettings
from fw_queue import keys, sessions
from fw_queue.sessions import Principal, token_hash

TOTP_PURPOSE = "totp"
_HASHER = PasswordHasher()
_DUMMY = _HASHER.hash(secrets.token_urlsafe(16))

# Atomic compare-and-set: accept a TOTP step only if it is newer than the last one used.
_STEP_CAS = """
local last = tonumber(redis.call('GET', KEYS[1]) or '-1')
if tonumber(ARGV[1]) <= last then return 0 end
redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2])
return 1
"""


class LockedOut(Exception):
    def __init__(self, retry_after_s: int) -> None:
        super().__init__("too many failed sign-ins")
        self.retry_after_s = retry_after_s


class BadCredentials(Exception):
    """Wrong email, password or code (deliberately not more specific)."""


@dataclass(frozen=True)
class _User:
    tenant_id: UUID
    id: UUID
    email: str
    name: str
    role: sessions.Role
    password_hash: str
    mfa_enabled: bool
    totp: Sealed | None


def hash_password(password: str) -> str:
    return _HASHER.hash(password)


def new_totp_secret() -> str:
    return pyotp.random_base32()


def seal_totp(envelope: Envelope, tenant_id: UUID, user_id: UUID, secret: str) -> Sealed:
    return envelope.seal(secret.encode(), aad_for(tenant_id, user_id, TOTP_PURPOSE))


def ip_prefix(ip: str | None) -> str | None:
    """Client address reduced to /24 (IPv4) or /48 (IPv6) for audit and lockout keys."""
    if not ip:
        return None
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return None
    net = ipaddress.ip_network(f"{addr}/{24 if addr.version == 4 else 48}", strict=False)
    return str(net)


class Auth:
    def __init__(
        self,
        cfg: AuthSettings,
        redis: Redis,
        engine: AsyncEngine,
        envelope: Envelope,
        shared_emails: frozenset[str] = frozenset(),
    ) -> None:
        self.cfg = cfg
        # Accounts whose password is public (the demo login): lock out per client address only,
        # or one visitor could lock everyone out by failing on purpose.
        self.shared_emails = shared_emails
        self.redis = redis
        self.engine = engine
        self.envelope = envelope
        self._cas = redis.register_script(_STEP_CAS)
        self._hash_slots = asyncio.Semaphore(cfg.hash_concurrency)

    # ---------------- step 1: password ----------------

    async def password_step(self, email: str, password: str, client_ip: str | None) -> str:
        """Returns a short-lived MFA token (cookie) after a correct password."""
        email = email.strip().lower()
        subjects = self._subjects(email, client_ip)
        await self._check_lock(subjects)
        await self._count_attempt(client_ip)
        user = await self._user(email)
        ok = await self._verify(user.password_hash if user else _DUMMY, password) and user is not None
        if not ok or user is None:
            await self._fail(subjects)
            raise BadCredentials
        if not user.mfa_enabled or user.totp is None:
            # every console account must have MFA; an account without it cannot sign in
            await self._fail(subjects)
            raise BadCredentials
        token = secrets.token_urlsafe(32)
        await self.redis.set(
            keys.mfa_pending(token_hash(token)),
            json.dumps({"tenant_id": str(user.tenant_id), "user_id": str(user.id), "email": email}),
            ex=self.cfg.mfa_pending_ttl_s,
        )
        return token

    # ---------------- step 2: TOTP ----------------

    async def mfa_step(self, mfa_token: str | None, code: str, client_ip: str | None) -> tuple[str, Principal]:
        if not mfa_token or len(mfa_token) > 200:
            raise BadCredentials
        pending_key = keys.mfa_pending(token_hash(mfa_token))
        raw = await self.redis.get(pending_key)
        if raw is None:
            raise BadCredentials
        pending = json.loads(raw)
        subjects = self._subjects(pending["email"], client_ip)
        await self._check_lock(subjects)
        user = await self._user(pending["email"])
        if user is None or user.totp is None or str(user.id) != pending["user_id"]:
            raise BadCredentials
        if not await self._totp_ok(user, code, single_use=pending["email"] not in self.shared_emails):
            await self._fail(subjects)
            raise BadCredentials
        await self.redis.delete(pending_key, *(keys.login_failures(s) for s in subjects if s.startswith("email:")))
        async with tenant_tx(self.engine, user.tenant_id) as conn:
            await conn.execute(
                text("UPDATE users SET last_seen_at = clock_timestamp() WHERE tenant_id = :t AND id = :u"),
                {"t": user.tenant_id, "u": user.id},
            )
            await conn.execute(
                text(
                    """INSERT INTO audit_log (tenant_id, actor, role, action, target, detail, ip_prefix)
                       VALUES (:t, :a, :r, 'auth.sign_in', 'console', 'password and one-time code', :ip)"""
                ),
                {"t": user.tenant_id, "a": user.email, "r": user.role, "ip": ip_prefix(client_ip)},
            )
        return await sessions.create(
            self.redis, Principal(user.tenant_id, user.role, user.id, user.email, user.name), self.cfg.session_ttl_s
        )

    async def current_code(self, email: str) -> str | None:
        """The live TOTP code of the public demo account. Refuses any other role, so a misconfigured
        demo email can never put a staff member's code on the public login page."""
        user = await self._user(email.strip().lower())
        if user is None or user.totp is None or user.role != "demo":
            return None
        return pyotp.TOTP(self._secret(user)).now()

    # ---------------- internals ----------------

    async def _verify(self, password_hash: str, password: str) -> bool:
        """argon2 off the event loop, a bounded number at a time."""
        async with self._hash_slots:
            try:
                return await asyncio.to_thread(_HASHER.verify, password_hash, password)
            except (VerificationError, InvalidHashError):
                return False

    async def _count_attempt(self, client_ip: str | None) -> None:
        prefix = ip_prefix(client_ip)
        if prefix is None:
            return
        key = keys.password_attempts(f"ip:{prefix}")
        async with self.redis.pipeline(transaction=True) as pipe:
            pipe.incr(key)
            pipe.expire(key, self.cfg.login_window_s, nx=True)
            pipe.ttl(key)
            count, _, ttl = await pipe.execute()
        if int(count) > self.cfg.password_attempts_per_window:
            raise LockedOut(max(int(ttl), 1))

    async def _totp_ok(self, user: _User, code: str, single_use: bool = True) -> bool:
        """A valid code for the current step (± the allowed drift). Personal accounts may use each
        step once. The shared demo account may not: its code is public and every visitor uses the
        same one; each sign-in still needs its own single-use password-step token."""
        code = code.strip().replace(" ", "")
        if not code.isdigit() or len(code) != 6:
            return False
        totp = pyotp.TOTP(self._secret(user))
        now = datetime.now(UTC)
        for drift in range(-self.cfg.totp_valid_window, self.cfg.totp_valid_window + 1):
            step = totp.timecode(now) + drift
            if secrets.compare_digest(totp.generate_otp(step), code):
                if not single_use:
                    return True
                ttl = totp.interval * (2 * self.cfg.totp_valid_window + 2)
                return bool(await self._cas(keys=[keys.totp_used(user.id)], args=[step, ttl]))
        return False

    def _secret(self, user: _User) -> str:
        assert user.totp is not None
        return self.envelope.open(user.totp, aad_for(user.tenant_id, user.id, TOTP_PURPOSE)).decode()

    async def _user(self, email: str) -> _User | None:
        async with system_tx(self.engine) as conn:
            row = (
                await conn.execute(text("SELECT tenant_id, user_id FROM user_directory WHERE email = :e"), {"e": email})
            ).one_or_none()
        if row is None:
            return None
        async with tenant_tx(self.engine, row.tenant_id) as conn:
            u = (
                await conn.execute(
                    text(
                        """SELECT id, email, name, role, password_hash, mfa_enabled,
                                  totp_key_id, totp_wrapped, totp_nonce, totp_sealed
                           FROM users WHERE tenant_id = :t AND id = :u"""
                    ),
                    {"t": row.tenant_id, "u": row.user_id},
                )
            ).one_or_none()
        if u is None:
            return None
        sealed = (
            Sealed(u.totp_key_id, u.totp_wrapped, u.totp_nonce, u.totp_sealed) if u.totp_sealed is not None else None
        )
        return _User(row.tenant_id, u.id, u.email, u.name, u.role, u.password_hash, u.mfa_enabled, sealed)

    def _subjects(self, email: str, client_ip: str | None) -> list[str]:
        by_ip = [f"ip:{p}"] if (p := ip_prefix(client_ip)) else []
        return by_ip if email in self.shared_emails else [f"email:{email}", *by_ip]

    async def _check_lock(self, subjects: list[str]) -> None:
        for subject in subjects:
            count = await self.redis.get(keys.login_failures(subject))
            if count is not None and int(count) >= self.cfg.login_max_attempts:
                ttl = await self.redis.ttl(keys.login_failures(subject))
                raise LockedOut(max(int(ttl), 1))

    async def _fail(self, subjects: list[str]) -> None:
        async with self.redis.pipeline(transaction=True) as pipe:
            for subject in subjects:
                key = keys.login_failures(subject)
                pipe.incr(key)
                pipe.expire(key, self.cfg.login_window_s, nx=True)
            results = await pipe.execute()
        for subject, count in zip(subjects, results[::2], strict=True):
            if int(count) >= self.cfg.login_max_attempts:
                await self.redis.expire(keys.login_failures(subject), self.cfg.lockout_s)
