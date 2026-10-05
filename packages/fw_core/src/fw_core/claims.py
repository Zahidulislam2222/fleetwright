"""The claim state machine: the part of Fleetwright that guarantees no job is acted on twice.

    DETECTED -> QUEUED -> LEASED -> ACTING -> CONFIRMED | FAILED | UNKNOWN -> RECONCILED

Rules (each enforced by the database, not by worker code):
1. One claim per (tenant, job key): a unique constraint picks exactly one winner.
2. Leasing takes a fresh fencing token from a sequence. Every later step names its token, and the
   UPDATE matches only if the token is still current, so a paused or stale worker is rejected.
3. Lease expiry is judged by the database clock, never by a worker clock.
4. Only a claim that never reached ACTING may go back to QUEUED. A claim whose worker vanished
   during ACTING becomes UNKNOWN and is never retried blindly: the reconciler checks the target.
5. At most one active lease per target account (partial unique index).

Every function runs inside a tenant transaction (fw_core.db.tenant_tx); RLS scopes all rows.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection


class ClaimState(StrEnum):
    DETECTED = "DETECTED"
    QUEUED = "QUEUED"
    LEASED = "LEASED"
    ACTING = "ACTING"
    CONFIRMED = "CONFIRMED"
    FAILED = "FAILED"
    UNKNOWN = "UNKNOWN"
    RECONCILED = "RECONCILED"


TERMINAL = frozenset({ClaimState.CONFIRMED, ClaimState.FAILED, ClaimState.RECONCILED})
DISPATCH_TOPIC = "claim.dispatch"


class AccountBusy(Exception):
    """The account already holds an active lease (the claim-level account mutex)."""


@dataclass(frozen=True)
class Detection:
    key: str
    lane: str
    rate_usd: int
    published_at: datetime | None
    seen_at: datetime  # corrected to the database clock by the watcher's measured offset
    clock_offset_ms: float | None
    payload: dict[str, Any]
    filter_id: UUID | None


@dataclass(frozen=True)
class Lease:
    claim_id: UUID
    fence: int
    target_job_key: str


async def _event(
    conn: AsyncConnection, tenant_id: UUID, claim_id: UUID, state: str, actor: str, note: str | None = None
) -> None:
    await conn.execute(
        text("INSERT INTO claim_events (tenant_id, claim_id, state, actor, note) VALUES (:t, :c, :s, :a, :n)"),
        {"t": tenant_id, "c": claim_id, "s": state, "a": actor, "n": note},
    )


async def _dispatch(conn: AsyncConnection, tenant_id: UUID, claim_id: UUID) -> None:
    await conn.execute(
        text("INSERT INTO outbox (tenant_id, topic, payload) VALUES (:t, :topic, CAST(:p AS jsonb))"),
        {"t": tenant_id, "topic": DISPATCH_TOPIC, "p": json.dumps({"claim_id": str(claim_id)})},
    )


async def queue_claim(conn: AsyncConnection, tenant_id: UUID, det: Detection, cell_id: str, actor: str) -> UUID | None:
    """Records the job and creates its claim in QUEUED, plus the dispatch message in the outbox, in
    one transaction. Returns None when another detection of the same job already won."""
    await conn.execute(
        text(
            """INSERT INTO target_jobs (tenant_id, key, published_at, first_seen_at, payload)
               VALUES (:t, :k, :p, :s, CAST(:payload AS jsonb)) ON CONFLICT (tenant_id, key) DO NOTHING"""
        ),
        {
            "t": tenant_id,
            "k": det.key,
            "p": det.published_at,
            "s": det.seen_at,
            "payload": json.dumps(det.payload, default=str),
        },
    )
    claim_id = uuid4()
    row = (
        await conn.execute(
            text(
                """INSERT INTO claims (tenant_id, id, target_job_key, state, filter_id, cell_id, lane, rate_usd,
                                      published_at, seen_at, clock_offset_ms)
                   VALUES (:t, :id, :k, 'QUEUED', :f, :cell, :lane, :rate, :p, :s, :off)
                   ON CONFLICT (tenant_id, target_job_key) DO NOTHING RETURNING id"""
            ),
            {
                "t": tenant_id,
                "id": claim_id,
                "k": det.key,
                "f": det.filter_id,
                "cell": cell_id,
                "lane": det.lane,
                "rate": det.rate_usd,
                "p": det.published_at,
                "s": det.seen_at,
                "off": det.clock_offset_ms,
            },
        )
    ).one_or_none()
    if row is None:
        return None
    await conn.execute(
        text("INSERT INTO claim_events (tenant_id, claim_id, at, state, actor) VALUES (:t, :c, :at, 'DETECTED', :a)"),
        {"t": tenant_id, "c": claim_id, "at": det.seen_at, "a": actor},
    )
    await _event(conn, tenant_id, claim_id, ClaimState.QUEUED, actor)
    await _dispatch(conn, tenant_id, claim_id)
    return claim_id


async def lease(
    conn: AsyncConnection,
    tenant_id: UUID,
    claim_id: UUID,
    *,
    worker_id: str,
    account_id: UUID,
    ttl_ms: int,
    max_age_s: int,
) -> Lease | None:
    """QUEUED -> LEASED with a fresh fencing token. None if the claim is gone, taken or too old.
    Raises AccountBusy if this account already holds an active lease."""
    try:
        async with conn.begin_nested():
            row = (
                await conn.execute(
                    text(
                        """UPDATE claims SET state = 'LEASED', fence = nextval('claim_fence'), worker_id = :w,
                                  account_id = :a, leased_at = clock_timestamp(),
                                  lease_expires_at = clock_timestamp() + make_interval(secs => :ttl / 1000.0)
                           WHERE tenant_id = :t AND id = :c AND state = 'QUEUED'
                             AND queued_at > clock_timestamp() - make_interval(secs => :age)
                           RETURNING fence, target_job_key"""
                    ),
                    {"t": tenant_id, "c": claim_id, "w": worker_id, "a": account_id, "ttl": ttl_ms, "age": max_age_s},
                )
            ).one_or_none()
    except IntegrityError as exc:
        if "claims_one_active_per_account" in str(exc.orig):
            raise AccountBusy(str(account_id)) from exc
        raise
    if row is None:
        return None
    await _event(conn, tenant_id, claim_id, ClaimState.LEASED, worker_id, f"fencing token {row.fence}")
    return Lease(claim_id, int(row.fence), str(row.target_job_key))


async def start_acting(conn: AsyncConnection, tenant_id: UUID, held: Lease, worker_id: str, ttl_ms: int) -> bool:
    """LEASED -> ACTING, only while this exact lease is current and unexpired (database clock).
    False means: do not act — the lease was lost."""
    row = (
        await conn.execute(
            text(
                """UPDATE claims SET state = 'ACTING', act_sent_at = clock_timestamp(),
                          lease_expires_at = clock_timestamp() + make_interval(secs => :ttl / 1000.0)
                   WHERE tenant_id = :t AND id = :c AND fence = :f AND state = 'LEASED'
                     AND lease_expires_at > clock_timestamp()
                   RETURNING id"""
            ),
            {"t": tenant_id, "c": held.claim_id, "f": held.fence, "ttl": ttl_ms},
        )
    ).one_or_none()
    if row is None:
        return False
    await _event(conn, tenant_id, held.claim_id, ClaimState.ACTING, worker_id)
    return True


Outcome = Literal["confirmed", "failed", "unknown"]


async def finish(
    conn: AsyncConnection, tenant_id: UUID, held: Lease, worker_id: str, outcome: Outcome, note: str
) -> str | None:
    """Records what the actor observed. Returns the new state, or None if the fence is stale.

    A late actor still knows the truth: if the reconciler already marked the claim UNKNOWN (or even
    resolved it as not booked) and the fence still matches, the actor's definite answer wins."""
    params = {"t": tenant_id, "c": held.claim_id, "f": held.fence, "n": note}
    if outcome == "unknown":
        row = (
            await conn.execute(
                text(
                    """UPDATE claims SET state = 'UNKNOWN', result = :n
                       WHERE tenant_id = :t AND id = :c AND fence = :f AND state = 'ACTING' RETURNING state"""
                ),
                params,
            )
        ).one_or_none()
    else:
        new_state = "CONFIRMED" if outcome == "confirmed" else "FAILED"
        resolution = "confirmed" if outcome == "confirmed" else "not_booked"
        row = (
            await conn.execute(
                text(
                    """UPDATE claims SET
                         state = CASE WHEN state = 'ACTING' THEN :s ELSE 'RECONCILED' END,
                         resolution = CASE WHEN state = 'ACTING' THEN resolution ELSE :r || '_by_late_actor' END,
                         confirmed_at = CASE WHEN :s = 'CONFIRMED' THEN clock_timestamp() ELSE confirmed_at END,
                         finished_at = clock_timestamp(), result = :n
                       WHERE tenant_id = :t AND id = :c AND fence = :f
                         AND (state IN ('ACTING', 'UNKNOWN') OR (state = 'RECONCILED' AND resolution = 'not_booked' AND :s = 'CONFIRMED'))
                       RETURNING state"""
                ),
                {**params, "s": new_state, "r": resolution},
            )
        ).one_or_none()
    if row is None:
        return None
    await _event(conn, tenant_id, held.claim_id, row.state, worker_id, note)
    return str(row.state)


# ---------------- reconciler side ----------------


@dataclass(frozen=True)
class Sweep:
    requeued: list[UUID]
    expired: list[UUID]
    unknown: list[UUID]


async def sweep_leases(conn: AsyncConnection, tenant_id: UUID, max_age_s: int, limit: int, actor: str) -> Sweep:
    """Applies the timeout rules (database clock):
    - LEASED past expiry, never acted: back to QUEUED and dispatched again (FAILED if too old);
    - ACTING past expiry: UNKNOWN (the action may have happened);
    - QUEUED older than max age: FAILED (expired).

    Each rule is ONE statement that also writes the history rows and outbox messages, so row locks
    are held for one round trip only. (Per-row follow-up statements kept the transaction open long
    enough to block workers re-leasing the same account under load.)"""
    params = {"t": tenant_id, "age": max_age_s, "n": limit, "actor": actor, "topic": DISPATCH_TOPIC}
    requeued = [
        r.id
        for r in await conn.execute(
            text(
                """WITH moved AS (
                     UPDATE claims SET state = 'QUEUED', worker_id = NULL, account_id = NULL, lease_expires_at = NULL,
                            leased_at = NULL, dispatches = dispatches + 1
                     WHERE (tenant_id, id) IN (
                       SELECT tenant_id, id FROM claims WHERE tenant_id = :t AND state = 'LEASED'
                         AND lease_expires_at < clock_timestamp() AND queued_at > clock_timestamp() - make_interval(secs => :age)
                       ORDER BY lease_expires_at LIMIT :n FOR UPDATE SKIP LOCKED)
                     RETURNING tenant_id, id),
                   history AS (
                     INSERT INTO claim_events (tenant_id, claim_id, state, actor, note)
                     SELECT tenant_id, id, 'QUEUED', :actor, 'lease expired before acting; dispatched again' FROM moved),
                   dispatch AS (
                     INSERT INTO outbox (tenant_id, topic, payload)
                     SELECT tenant_id, :topic, jsonb_build_object('claim_id', id) FROM moved)
                   SELECT id FROM moved"""
            ),
            params,
        )
    ]
    expired = [
        r.id
        for r in await conn.execute(
            text(
                """WITH moved AS (
                     UPDATE claims SET state = 'FAILED', finished_at = clock_timestamp(), result = 'expired before an actor took it',
                            worker_id = NULL, account_id = NULL, lease_expires_at = NULL
                     WHERE (tenant_id, id) IN (
                       SELECT tenant_id, id FROM claims WHERE tenant_id = :t
                         AND ((state = 'QUEUED' AND queued_at < clock_timestamp() - make_interval(secs => :age))
                           OR (state = 'LEASED' AND lease_expires_at < clock_timestamp()
                               AND queued_at <= clock_timestamp() - make_interval(secs => :age)))
                       LIMIT :n FOR UPDATE SKIP LOCKED)
                     RETURNING tenant_id, id),
                   history AS (
                     INSERT INTO claim_events (tenant_id, claim_id, state, actor, note)
                     SELECT tenant_id, id, 'FAILED', :actor, 'expired before an actor took it' FROM moved)
                   SELECT id FROM moved"""
            ),
            params,
        )
    ]
    unknown = [
        r.id
        for r in await conn.execute(
            text(
                """WITH moved AS (
                     UPDATE claims SET state = 'UNKNOWN', result = 'worker lost before confirmation'
                     WHERE (tenant_id, id) IN (
                       SELECT tenant_id, id FROM claims WHERE tenant_id = :t AND state = 'ACTING'
                         AND lease_expires_at < clock_timestamp()
                       LIMIT :n FOR UPDATE SKIP LOCKED)
                     RETURNING tenant_id, id),
                   history AS (
                     INSERT INTO claim_events (tenant_id, claim_id, state, actor, note)
                     SELECT tenant_id, id, 'UNKNOWN', :actor, 'worker lost before confirmation' FROM moved)
                   SELECT id FROM moved"""
            ),
            params,
        )
    ]
    return Sweep(requeued, expired, unknown)


@dataclass(frozen=True)
class UnknownClaim:
    claim_id: UUID
    account_id: UUID
    target_job_key: str


async def unknown_claims(conn: AsyncConnection, tenant_id: UUID, grace_ms: int, limit: int) -> list[UnknownClaim]:
    """UNKNOWN claims older than the grace period, oldest first. No row locks: the caller checks the
    target over the network next, and resolve_unknown() is conditional (state = 'UNKNOWN'), so two
    reconcilers checking the same claim is harmless."""
    rows = await conn.execute(
        text(
            """SELECT id, account_id, target_job_key FROM claims
               WHERE tenant_id = :t AND state = 'UNKNOWN'
                 AND lease_expires_at < clock_timestamp() - make_interval(secs => :g / 1000.0)
               ORDER BY lease_expires_at LIMIT :n"""
        ),
        {"t": tenant_id, "g": grace_ms, "n": limit},
    )
    return [UnknownClaim(r.id, r.account_id, r.target_job_key) for r in rows]


async def resolve_unknown(
    conn: AsyncConnection, tenant_id: UUID, claim_id: UUID, booked: bool, actor: str, note: str
) -> bool:
    """UNKNOWN -> RECONCILED after checking the target. Never re-dispatches the job."""
    row = (
        await conn.execute(
            text(
                """UPDATE claims SET state = 'RECONCILED', resolution = :r, finished_at = clock_timestamp(),
                          confirmed_at = CASE WHEN :booked THEN clock_timestamp() ELSE confirmed_at END
                   WHERE tenant_id = :t AND id = :c AND state = 'UNKNOWN' RETURNING id"""
            ),
            {"t": tenant_id, "c": claim_id, "r": "confirmed" if booked else "not_booked", "booked": booked},
        )
    ).one_or_none()
    if row is None:
        return False
    await _event(conn, tenant_id, claim_id, ClaimState.RECONCILED, actor, note)
    return True
