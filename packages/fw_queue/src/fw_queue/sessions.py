"""Console sessions in core Redis, shared by the API (creates them) and the event gateway (reads
them). The browser holds a random token in an httpOnly cookie; Redis stores only its SHA-256, so a
Redis dump does not hand out live sessions."""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import asdict, dataclass
from typing import Literal
from uuid import UUID

from redis.asyncio import Redis

from fw_queue import keys

Role = Literal["owner", "operator", "viewer", "demo", "public"]
RANK: dict[Role, int] = {"public": 0, "viewer": 1, "demo": 1, "operator": 2, "owner": 3}


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


@dataclass(frozen=True)
class Principal:
    """Who is asking. `public` is an anonymous visitor of the demo tenant (read-only, redacted)."""

    tenant_id: UUID
    role: Role
    user_id: UUID | None = None
    email: str | None = None
    name: str | None = None
    csrf: str | None = None
    session: str | None = None  # token hash

    def at_least(self, role: Role) -> bool:
        return RANK[self.role] >= RANK[role]

    @property
    def redacted(self) -> bool:
        """Personal data (emails, client addresses) is hidden from anonymous and demo viewers."""
        return self.role in ("public", "demo")


async def create(redis: Redis, principal: Principal, ttl_s: int) -> tuple[str, Principal]:
    """New session; returns the cookie token and the principal carrying its CSRF token."""
    token = secrets.token_urlsafe(32)
    digest = token_hash(token)
    full = Principal(
        principal.tenant_id,
        principal.role,
        principal.user_id,
        principal.email,
        principal.name,
        secrets.token_urlsafe(24),
        digest,
    )
    record = {k: (str(v) if isinstance(v, UUID) else v) for k, v in asdict(full).items()}
    async with redis.pipeline(transaction=True) as pipe:
        pipe.set(keys.session(digest), json.dumps(record), ex=ttl_s)
        if full.user_id is not None:
            pipe.sadd(keys.user_sessions(full.user_id), digest)
            pipe.expire(keys.user_sessions(full.user_id), ttl_s)
        await pipe.execute()
    return token, full


async def load(redis: Redis, token: str | None) -> Principal | None:
    if not token or len(token) > 200:
        return None
    raw = await redis.get(keys.session(token_hash(token)))
    if raw is None:
        return None
    data = json.loads(raw)
    return Principal(
        UUID(data["tenant_id"]),
        data["role"],
        UUID(data["user_id"]) if data.get("user_id") else None,
        data.get("email"),
        data.get("name"),
        data.get("csrf"),
        data.get("session"),
    )


async def revoke(redis: Redis, principal: Principal) -> None:
    if principal.session is None:
        return
    async with redis.pipeline(transaction=True) as pipe:
        pipe.delete(keys.session(principal.session))
        if principal.user_id is not None:
            pipe.srem(keys.user_sessions(principal.user_id), principal.session)
        await pipe.execute()


async def revoke_all(redis: Redis, user_id: UUID) -> int:
    members = [m.decode() if isinstance(m, bytes) else m for m in await redis.smembers(keys.user_sessions(user_id))]
    if not members:
        return 0
    await redis.delete(*(keys.session(m) for m in members), keys.user_sessions(user_id))
    return len(members)
