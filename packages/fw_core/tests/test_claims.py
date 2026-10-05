"""Phase 3 exit criteria 1-3: the claim state machine never lets one job be acted on twice, survives
worker crashes in every state, and never retries an UNKNOWN claim blindly."""

from __future__ import annotations

import asyncio
import random
from collections import Counter
from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st
from sqlalchemy import text

from dbkit import Db, new_accounts, new_tenant
from fw_core import claims
from fw_core.claims import AccountBusy, Detection, Lease
from fw_core.db import tenant_tx

pytestmark = pytest.mark.integration

TTL_MS = 300
MAX_AGE_S = 120


def detection(key: str) -> Detection:
    now = datetime.now(UTC)
    return Detection(key, "Dallas, TX → Memphis, TN", 1800, now, now, 0.0, {"ref": key}, None)


async def queue(db: Db, t: UUID, key: str) -> UUID | None:
    async with tenant_tx(db.app, t) as conn:
        return await claims.queue_claim(conn, t, detection(key), "cell-a", "test-dispatcher")


async def lease(
    db: Db, t: UUID, claim_id: UUID, worker: str, account: UUID, ttl_ms: int = TTL_MS, max_age_s: int = MAX_AGE_S
) -> Lease | None:
    async with tenant_tx(db.worker, t) as conn:
        return await claims.lease(
            conn, t, claim_id, worker_id=worker, account_id=account, ttl_ms=ttl_ms, max_age_s=max_age_s
        )


async def act(db: Db, t: UUID, held: Lease, worker: str, ttl_ms: int = TTL_MS) -> bool:
    async with tenant_tx(db.worker, t) as conn:
        return await claims.start_acting(conn, t, held, worker, ttl_ms)


async def finish(db: Db, t: UUID, held: Lease, worker: str, outcome: claims.Outcome) -> str | None:
    async with tenant_tx(db.worker, t) as conn:
        return await claims.finish(conn, t, held, worker, outcome, outcome)


async def sweep(db: Db, t: UUID, max_age_s: int = MAX_AGE_S) -> claims.Sweep:
    async with tenant_tx(db.app, t) as conn:
        return await claims.sweep_leases(conn, t, max_age_s, 1000, "test-reconciler")


async def state_of(db: Db, t: UUID, claim_id: UUID) -> tuple[str, str | None, int | None]:
    async with tenant_tx(db.app, t) as conn:
        row = (
            await conn.execute(text("SELECT state, resolution, fence FROM claims WHERE id = :c"), {"c": claim_id})
        ).one()
        return row.state, row.resolution, row.fence


async def outbox_rows(db: Db, t: UUID, claim_id: UUID) -> int:
    async with tenant_tx(db.app, t) as conn:
        return int(
            (
                await conn.execute(
                    text("SELECT count(*) FROM outbox WHERE payload->>'claim_id' = :c"), {"c": str(claim_id)}
                )
            ).scalar_one()
        )


# ---------------- single-claim behaviour ----------------


async def test_happy_path_and_event_history(db: Db) -> None:
    t = await new_tenant(db)
    (acct,) = await new_accounts(db, t, 1)
    claim_id = await queue(db, t, "L-1")
    assert claim_id is not None
    held = await lease(db, t, claim_id, "w1", acct)
    assert held is not None and held.fence > 0
    assert await act(db, t, held, "w1")
    assert await finish(db, t, held, "w1", "confirmed") == "CONFIRMED"
    async with tenant_tx(db.app, t) as conn:
        history = [
            r.state
            for r in await conn.execute(
                text("SELECT state FROM claim_events WHERE claim_id = :c ORDER BY id"), {"c": claim_id}
            )
        ]
    assert history == ["DETECTED", "QUEUED", "LEASED", "ACTING", "CONFIRMED"]
    assert await outbox_rows(db, t, claim_id) == 1


async def test_second_detection_of_the_same_job_loses(db: Db) -> None:
    t = await new_tenant(db)
    first, second = await asyncio.gather(queue(db, t, "L-2"), queue(db, t, "L-2"))
    assert sorted([first is None, second is None]) == [False, True]


async def test_only_one_of_many_leases_wins(db: Db) -> None:
    t = await new_tenant(db)
    accounts = await new_accounts(db, t, 20)
    claim_id = await queue(db, t, "L-3")
    assert claim_id is not None
    results = await asyncio.gather(*(lease(db, t, claim_id, f"w{i}", a) for i, a in enumerate(accounts)))
    assert sum(r is not None for r in results) == 1


async def test_stale_fence_cannot_act(db: Db) -> None:
    t = await new_tenant(db)
    (acct,) = await new_accounts(db, t, 1)
    claim_id = await queue(db, t, "L-4")
    assert claim_id is not None
    held = await lease(db, t, claim_id, "w1", acct, ttl_ms=50)
    assert held is not None
    await asyncio.sleep(0.12)  # the lease expires on the database clock
    assert not await act(db, t, held, "w1"), "an expired lease must not start acting"


async def test_crash_between_leased_and_acting_releases_the_job(db: Db) -> None:
    t = await new_tenant(db)
    a1, a2 = await new_accounts(db, t, 2)
    claim_id = await queue(db, t, "L-5")
    assert claim_id is not None
    dead = await lease(db, t, claim_id, "w-dead", a1, ttl_ms=80)
    assert dead is not None
    await asyncio.sleep(0.15)
    result = await sweep(db, t)
    assert claim_id in result.requeued
    assert await outbox_rows(db, t, claim_id) == 2, "re-queued claims are dispatched again through the outbox"
    fresh = await lease(db, t, claim_id, "w-live", a2)
    assert fresh is not None and fresh.fence > dead.fence
    assert not await act(db, t, dead, "w-dead"), "the old worker's fence is stale"
    assert await act(db, t, fresh, "w-live")
    assert await finish(db, t, fresh, "w-live", "confirmed") == "CONFIRMED"


async def test_crash_during_acting_goes_unknown_and_is_reconciled_not_retried(db: Db) -> None:
    t = await new_tenant(db)
    (acct,) = await new_accounts(db, t, 1)
    booked_id = await queue(db, t, "L-6")
    lost_id = await queue(db, t, "L-7")
    assert booked_id and lost_id
    for claim_id, booked in ((booked_id, True), (lost_id, False)):
        held = await lease(db, t, claim_id, "w-dying", acct, ttl_ms=60)
        assert held is not None and await act(db, t, held, "w-dying", ttl_ms=60)
        await asyncio.sleep(0.12)
        assert claim_id in (await sweep(db, t)).unknown
        assert await outbox_rows(db, t, claim_id) == 1, "UNKNOWN must never be dispatched again"
        async with tenant_tx(db.app, t) as conn:
            pending = await claims.unknown_claims(conn, t, grace_ms=0, limit=10)
            assert [p.claim_id for p in pending] == [claim_id]
            assert await claims.resolve_unknown(conn, t, claim_id, booked, "test-reconciler", "checked my bookings")
        assert await state_of(db, t, claim_id) == ("RECONCILED", "confirmed" if booked else "not_booked", held.fence)


async def test_late_actor_answer_resolves_unknown(db: Db) -> None:
    t = await new_tenant(db)
    (acct,) = await new_accounts(db, t, 1)
    claim_id = await queue(db, t, "L-8")
    assert claim_id is not None
    held = await lease(db, t, claim_id, "w-slow", acct, ttl_ms=60)
    assert held is not None and await act(db, t, held, "w-slow", ttl_ms=60)
    await asyncio.sleep(0.12)
    await sweep(db, t)
    assert (await state_of(db, t, claim_id))[0] == "UNKNOWN"
    assert await finish(db, t, held, "w-slow", "confirmed") == "RECONCILED"
    assert (await state_of(db, t, claim_id))[1] == "confirmed_by_late_actor"


async def test_account_mutex_one_active_lease_per_account(db: Db) -> None:
    t = await new_tenant(db)
    (acct,) = await new_accounts(db, t, 1)
    c1, c2 = await queue(db, t, "L-9"), await queue(db, t, "L-10")
    assert c1 and c2
    assert await lease(db, t, c1, "w1", acct) is not None
    with pytest.raises(AccountBusy):
        await lease(db, t, c2, "w2", acct)


async def test_queued_claim_that_nobody_takes_expires(db: Db) -> None:
    t = await new_tenant(db)
    claim_id = await queue(db, t, "L-11")
    assert claim_id is not None
    async with tenant_tx(db.app, t) as conn:
        await conn.execute(
            text("UPDATE claims SET queued_at = queued_at - interval '1 hour' WHERE id = :c"), {"c": claim_id}
        )
    assert claim_id in (await sweep(db, t)).expired
    assert (await state_of(db, t, claim_id))[0] == "FAILED"


# ---------------- property test: random interleavings ----------------

OPS = st.lists(
    st.tuples(
        st.sampled_from(["lease", "act", "finish_ok", "finish_fail", "finish_unknown", "crash", "sweep", "wait"]),
        st.integers(0, 3),
    ),
    min_size=5,
    max_size=40,
)


@settings(max_examples=40, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(ops=OPS)
async def test_random_interleavings_never_act_twice(db: Db, ops: list[tuple[str, int]]) -> None:
    """Four workers race on one job through random operation sequences, including crashes and lease
    expiry. Invariants: at most one worker ever acts; fences only grow; terminal states stick."""
    t = await new_tenant(db)
    accounts = await new_accounts(db, t, 4)
    claim_id = await queue(db, t, "L-P")
    assert claim_id is not None
    held: dict[int, Lease] = {}
    acted_with: set[int] = set()
    fences: list[int] = []
    terminal_seen: str | None = None
    for op, w in ops:
        worker = f"w{w}"
        if op == "lease" and w not in held:
            try:
                got = await lease(db, t, claim_id, worker, accounts[w], ttl_ms=40)
            except AccountBusy:
                got = None
            if got is not None:
                held[w] = got
                fences.append(got.fence)
        elif op == "act" and w in held:
            if await act(db, t, held[w], worker, ttl_ms=40):
                acted_with.add(held[w].fence)
        elif op.startswith("finish") and w in held:
            await finish(
                db,
                t,
                held[w],
                worker,
                {"finish_ok": "confirmed", "finish_fail": "failed", "finish_unknown": "unknown"}[op],
            )  # type: ignore[arg-type]
        elif op == "crash":
            held.pop(w, None)
        elif op == "sweep":
            await sweep(db, t)
        elif op == "wait":
            await asyncio.sleep(0.05)
        state, _, _ = await state_of(db, t, claim_id)
        if terminal_seen is not None:
            assert state == terminal_seen, f"terminal state changed: {terminal_seen} -> {state}"
        if state in ("CONFIRMED", "FAILED", "RECONCILED"):
            terminal_seen = state
    assert len(acted_with) <= 1, f"more than one lease reached ACTING: {acted_with}"
    assert fences == sorted(fences) and len(set(fences)) == len(fences)


# ---------------- the big one: 200 competitors x 10,000 jobs ----------------


@dataclass
class Target:
    """A strict fake target: counts every action attempt per job (the board's first-booker-wins would
    hide a duplicate attempt, so we count attempts, not successful bookings)."""

    attempts: Counter[str] = field(default_factory=Counter)
    booked_by: dict[str, str] = field(default_factory=dict)

    def act(self, key: str, worker: str) -> bool:
        self.attempts[key] += 1
        if key in self.booked_by:
            return False
        self.booked_by[key] = worker
        return True


@pytest.mark.slow
async def test_200_competitors_10000_jobs_zero_duplicate_actions(db: Db) -> None:
    jobs, competitors, sightings = 10_000, 200, 3  # each job is seen by 3 competitors (3 watchers)
    # Production-like timings. 200 coroutines in one process are slow; a 300 ms lease would expire
    # before most actors act, and the run would barely exercise ACTING (seen in the first attempt).
    ttl_ms, max_age_s = 5000, 900
    t = await new_tenant(db)
    accounts = await new_accounts(db, t, competitors)
    target = Target()
    queue_: asyncio.Queue[str] = asyncio.Queue()
    order = [f"J{n:05d}" for n in range(jobs) for _ in range(sightings)]
    random.Random(7).shuffle(order)
    for key in order:
        queue_.put_nowait(key)
    crashes = Counter[str]()
    claim_ids: dict[str, UUID] = {}

    async def competitor(n: int) -> None:
        rng = random.Random(n)
        worker, account = f"c{n}", accounts[n]
        while True:
            try:
                key = queue_.get_nowait()
            except asyncio.QueueEmpty:
                return
            claim_id = await queue(db, t, key) or claim_ids.get(key)
            if claim_id is None:
                async with tenant_tx(db.app, t) as conn:
                    claim_id = (
                        await conn.execute(text("SELECT id FROM claims WHERE target_job_key = :k"), {"k": key})
                    ).scalar_one()
            claim_ids[key] = claim_id
            try:
                held = await lease(db, t, claim_id, worker, account, ttl_ms, max_age_s)
            except AccountBusy:
                await asyncio.sleep(0.5)
                queue_.put_nowait(key)
                continue
            if held is None:
                continue
            roll = rng.random()
            if roll < 0.02:  # crash after LEASED: the account stays busy until the lease expires
                crashes["leased"] += 1
                await asyncio.sleep(ttl_ms / 1000 * 1.2)
                continue
            if not await act(db, t, held, worker, ttl_ms):
                crashes["lease_lost_before_acting"] += 1
                continue
            if roll < 0.04:  # crash during ACTING, after the request reached the target half the time
                crashes["acting"] += 1
                if roll < 0.03:
                    target.act(key, worker)
                await asyncio.sleep(ttl_ms / 1000 * 1.2)
                continue
            booked = target.act(key, worker)
            await finish(db, t, held, worker, "confirmed" if booked else "failed")

    async def reconciler(stop: asyncio.Event) -> None:
        while not stop.is_set():
            result = await sweep(db, t, max_age_s)
            async with tenant_tx(db.app, t) as conn:
                if result.requeued:
                    keys = await conn.execute(
                        text("SELECT target_job_key FROM claims WHERE id = ANY(:c)"), {"c": result.requeued}
                    )
                    for (key,) in keys:
                        queue_.put_nowait(key)
                pending = await claims.unknown_claims(conn, t, grace_ms=0, limit=200)
                workers = dict(
                    (
                        await conn.execute(
                            text("SELECT id, worker_id FROM claims WHERE id = ANY(:c)"),
                            {"c": [u.claim_id for u in pending]},
                        )
                    ).all()  # type: ignore[arg-type]
                )
            for u in pending:  # like the real reconciler: check the target outside any transaction, then a short update
                booked = target.booked_by.get(u.target_job_key) == workers[u.claim_id]
                async with tenant_tx(db.app, t) as conn:
                    await claims.resolve_unknown(conn, t, u.claim_id, booked, "test-reconciler", "checked the target")
            await asyncio.sleep(0.05)

    stop = asyncio.Event()
    rec = asyncio.create_task(reconciler(stop))
    started = asyncio.get_running_loop().time()
    while True:
        await asyncio.gather(*(competitor(n) for n in range(competitors)))
        await asyncio.sleep(ttl_ms / 1000 * 1.5)  # let the reconciler re-queue anything left behind
        if queue_.empty():
            async with tenant_tx(db.app, t) as conn:
                open_left = (
                    await conn.execute(
                        text("SELECT count(*) FROM claims WHERE state IN ('QUEUED', 'LEASED', 'ACTING', 'UNKNOWN')")
                    )
                ).scalar_one()
            if open_left == 0:
                break
        assert asyncio.get_running_loop().time() - started < 900, "did not converge"
    stop.set()
    await rec

    duplicates = {k: n for k, n in target.attempts.items() if n > 1}
    assert not duplicates, f"duplicate actions on {len(duplicates)} jobs, e.g. {list(duplicates.items())[:5]}"
    async with tenant_tx(db.app, t) as conn:
        rows = dict(
            (await conn.execute(text("SELECT coalesce(resolution, state), count(*) FROM claims GROUP BY 1"))).all()  # type: ignore[arg-type]
        )
    confirmed = rows.get("CONFIRMED", 0) + rows.get("confirmed", 0) + rows.get("confirmed_by_late_actor", 0)
    assert sum(rows.values()) == jobs
    assert confirmed == len(target.booked_by), (rows, len(target.booked_by))
    reconciled = rows.get("confirmed", 0) + rows.get("not_booked", 0) + rows.get("confirmed_by_late_actor", 0)
    assert crashes["acting"] > 0 and reconciled > 0, ("the run must exercise crashes during ACTING", rows, crashes)
    assert len(target.booked_by) >= jobs * 0.95, f"only {len(target.booked_by)} of {jobs} jobs were booked: {rows}"
    print(
        f"\n{jobs} jobs, {competitors} competitors: states={rows}, crashes={dict(crashes)}, target bookings={len(target.booked_by)}"
    )
