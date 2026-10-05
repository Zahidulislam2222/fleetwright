"""Per-stage latency of the claim pipeline, from the timestamps on each claim (database clock;
`seen_at` is the watcher's time corrected by its measured clock offset):

    published -> seen -> queued -> leased -> act sent -> confirmed
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

STAGES = ("detect", "dispatch", "lease", "act", "confirm", "end_to_end")


@dataclass(frozen=True)
class StageLatency:
    stage: str
    samples: int
    p50_ms: float | None
    p95_ms: float | None
    p99_ms: float | None
    max_ms: float | None


_QUERY = text(
    """SELECT v.stage, count(*) AS n,
              percentile_cont(0.50) WITHIN GROUP (ORDER BY v.ms) AS p50,
              percentile_cont(0.95) WITHIN GROUP (ORDER BY v.ms) AS p95,
              percentile_cont(0.99) WITHIN GROUP (ORDER BY v.ms) AS p99,
              max(v.ms) AS mx
       FROM claims c
       CROSS JOIN LATERAL (VALUES
         ('detect',     extract(epoch FROM c.seen_at - c.published_at) * 1000),
         ('dispatch',   extract(epoch FROM c.queued_at - c.seen_at) * 1000),
         ('lease',      extract(epoch FROM c.leased_at - c.queued_at) * 1000),
         ('act',        extract(epoch FROM c.act_sent_at - c.leased_at) * 1000),
         ('confirm',    extract(epoch FROM c.confirmed_at - c.act_sent_at) * 1000),
         ('end_to_end', extract(epoch FROM c.confirmed_at - c.published_at) * 1000)
       ) AS v(stage, ms)
       WHERE c.tenant_id = :t AND c.queued_at >= :since AND v.ms IS NOT NULL
       GROUP BY v.stage"""
)


async def stage_latency(conn: AsyncConnection, tenant_id: UUID, since: datetime) -> list[StageLatency]:
    rows = {r.stage: r for r in await conn.execute(_QUERY, {"t": tenant_id, "since": since})}
    out = []
    for stage in STAGES:
        r = rows.get(stage)
        out.append(
            StageLatency(stage, 0, None, None, None, None)
            if r is None
            else StageLatency(stage, int(r.n), float(r.p50), float(r.p95), float(r.p99), float(r.mx))
        )
    return out
