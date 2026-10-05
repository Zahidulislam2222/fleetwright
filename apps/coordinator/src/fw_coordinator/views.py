"""Read models for the console, in the shapes of apps/dashboard/src/mocks/types.ts (the contract).
Every query runs in a tenant transaction (RLS). Personal data is masked for redacted viewers."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from fw_core.latency import stage_latency
from fw_core.settings import ApiSettings
from fw_core.timeutil import iso

LATENCY_KEYS = {
    "detect": "publish_to_seen",
    "dispatch": "seen_to_queued",
    "lease": "queued_to_leased",
    "act": "leased_to_act",
    "confirm": "act_to_confirmed",
}


def mask_email(email: str | None) -> str | None:
    if not email or "@" not in email:
        return email
    local, domain = email.split("@", 1)
    return f"{local[:1]}•••@{domain.split('.', 1)[0][:1]}•••"


def page(tenant_id: UUID, items: list[dict[str, Any]], next_cursor: str | None, total: int) -> dict[str, Any]:
    return {"tenant_id": str(tenant_id), "items": items, "next_cursor": next_cursor, "total_estimate": total}


def _encode_cursor(at: datetime, key: str) -> str:
    return base64.urlsafe_b64encode(f"{at.isoformat()}|{key}".encode()).decode()


def _decode_cursor(cursor: str | None) -> tuple[datetime, str] | None:
    if not cursor:
        return None
    try:
        at, key = base64.urlsafe_b64decode(cursor.encode()).decode().split("|", 1)
        return datetime.fromisoformat(at), key
    except (ValueError, binascii.Error, UnicodeDecodeError):
        return None


# ---------------- claims ----------------

_CLAIMS_PAGE = text(
    """SELECT id, target_job_key, lane, rate_usd, state, worker_id, account_id, fence, published_at, seen_at,
              queued_at, leased_at, act_sent_at, confirmed_at, resolution, result
       FROM claims
       WHERE tenant_id = :t AND (CAST(:state AS text) IS NULL OR state = :state)
         AND (CAST(:at AS timestamptz) IS NULL OR (queued_at, id::text) < (CAST(:at AS timestamptz), :key))
       ORDER BY queued_at DESC, id::text DESC LIMIT :n"""
)
_CLAIM_ONE = text(
    """SELECT id, target_job_key, lane, rate_usd, state, worker_id, account_id, fence, published_at, seen_at,
              queued_at, leased_at, act_sent_at, confirmed_at, resolution, result
       FROM claims WHERE tenant_id = :t AND id = :c"""
)


def _claim(tenant_id: UUID, r: Any) -> dict[str, Any]:
    return {
        "tenant_id": str(tenant_id),
        "id": str(r.id),
        "target_job_key": r.target_job_key,
        "lane": r.lane,
        "rate_usd": r.rate_usd,
        "state": r.state,
        "resolution": r.resolution,
        "result": r.result,
        "worker_id": r.worker_id,
        "account_id": str(r.account_id) if r.account_id else None,
        "fencing_token": r.fence,
        "published_at": iso(r.published_at),
        "seen_at": iso(r.seen_at),
        "queued_at": iso(r.queued_at),
        "leased_at": iso(r.leased_at),
        "act_sent_at": iso(r.act_sent_at),
        "confirmed_at": iso(r.confirmed_at),
        "events": [],
    }


async def claims(
    conn: AsyncConnection, tenant_id: UUID, cursor: str | None, limit: int, state: str | None
) -> dict[str, Any]:
    after = _decode_cursor(cursor)
    rows = (
        await conn.execute(
            _CLAIMS_PAGE,
            {
                "t": tenant_id,
                "state": state,
                "at": after[0] if after else None,
                "key": after[1] if after else "",
                "n": limit + 1,
            },
        )
    ).all()
    total = (
        await conn.execute(
            text(
                "SELECT count(*) FROM claims WHERE tenant_id = :t AND (CAST(:state AS text) IS NULL OR state = :state)"
            ),
            {"t": tenant_id, "state": state},
        )
    ).scalar_one()
    more = len(rows) > limit
    rows = rows[:limit]
    nxt = _encode_cursor(rows[-1].queued_at, str(rows[-1].id)) if more and rows else None
    return page(tenant_id, [_claim(tenant_id, r) for r in rows], nxt, int(total))


async def claim(conn: AsyncConnection, tenant_id: UUID, claim_id: UUID) -> dict[str, Any] | None:
    r = (
        await conn.execute(
            _CLAIM_ONE,
            {"t": tenant_id, "c": claim_id},
        )
    ).one_or_none()
    if r is None:
        return None
    out = _claim(tenant_id, r)
    out["events"] = [
        {"at": iso(e.at), "state": e.state, "actor": e.actor, "note": e.note}
        for e in await conn.execute(
            text("SELECT at, state, actor, note FROM claim_events WHERE tenant_id = :t AND claim_id = :c ORDER BY id"),
            {"t": tenant_id, "c": claim_id},
        )
    ]
    return out


# ---------------- workers ----------------


async def workers(conn: AsyncConnection, tenant_id: UUID, cfg: ApiSettings) -> dict[str, Any]:
    rows = (
        await conn.execute(
            text(
                """SELECT id, cell_id, mode, state, account_id, memory_mb, cpu_pct, version, started_at,
                          extract(epoch FROM clock_timestamp() - heartbeat_at) AS age
                   FROM workers WHERE tenant_id = :t AND heartbeat_at > clock_timestamp() - make_interval(secs => :recent)
                   ORDER BY id"""
            ),
            {"t": tenant_id, "recent": cfg.worker_recent_s},
        )
    ).all()
    items = []
    for r in rows:
        age = float(r.age)
        if r.state == "stopped" or age >= cfg.worker_dead_after_s:
            status = "dead"
        elif r.state == "draining":
            status = "draining"
        elif age >= cfg.worker_stale_after_s:
            status = "stale"
        else:
            status = "healthy"
        items.append(
            {
                "tenant_id": str(tenant_id),
                "id": r.id,
                "cell_id": r.cell_id,
                "mode": r.mode,
                "status": status,
                "account_id": str(r.account_id) if r.account_id else None,
                "contexts": 1,
                "memory_mb": r.memory_mb or 0,
                "cpu_pct": round(float(r.cpu_pct or 0), 1),
                "heartbeat_age_s": round(age, 1),
                "version": r.version,
                "started_at": iso(r.started_at),
            }
        )
    return page(tenant_id, items, None, len(items))


# ---------------- accounts ----------------


async def accounts(conn: AsyncConnection, tenant_id: UUID) -> dict[str, Any]:
    rows = (
        await conn.execute(
            text(
                """SELECT a.id, a.label, a.target, a.otp_channel, a.rate_limit_per_min, a.enabled,
                          s.state AS session_state, s.ttl_s, s.refreshed_at,
                          extract(epoch FROM s.expires_at - clock_timestamp()) AS expires_in,
                          (SELECT c.id FROM claims c WHERE c.tenant_id = a.tenant_id AND c.account_id = a.id
                             AND c.state IN ('LEASED', 'ACTING') LIMIT 1) AS active_lease
                   FROM accounts a LEFT JOIN account_sessions s ON s.tenant_id = a.tenant_id AND s.account_id = a.id
                   WHERE a.tenant_id = :t ORDER BY a.label"""
            ),
            {"t": tenant_id},
        )
    ).all()
    items = []
    for r in rows:
        expires_in = max(0, int(r.expires_in)) if r.expires_in is not None else 0
        state = r.session_state or "otp_required"
        if state == "fresh" and r.ttl_s and expires_in < 0.3 * r.ttl_s:
            state = "expiring"
        if r.expires_in is not None and r.expires_in <= 0:
            state = "expired"
        items.append(
            {
                "tenant_id": str(tenant_id),
                "id": str(r.id),
                "label": r.label,
                "target": r.target,
                "enabled": r.enabled,
                "session_state": state,
                "session_expires_in_s": expires_in,
                "session_ttl_s": r.ttl_s or 0,
                "last_refresh_at": iso(r.refreshed_at),
                "otp_channel": r.otp_channel,
                "active_lease": str(r.active_lease) if r.active_lease else None,
                "rate_limit_per_min": r.rate_limit_per_min,
            }
        )
    return page(tenant_id, items, None, len(items))


# ---------------- filters and schedules ----------------


async def filters(conn: AsyncConnection, tenant_id: UUID) -> dict[str, Any]:
    rows = (
        await conn.execute(
            text(
                """SELECT f.*, (SELECT count(*) FROM claims c WHERE c.tenant_id = f.tenant_id AND c.filter_id = f.id
                                   AND c.queued_at > clock_timestamp() - interval '24 hours') AS matched
                   FROM filters f WHERE f.tenant_id = :t ORDER BY f.name"""
            ),
            {"t": tenant_id},
        )
    ).all()
    items = [
        {
            "tenant_id": str(tenant_id),
            "id": str(r.id),
            "name": r.name,
            "enabled": r.enabled,
            "origin": r.origin,
            "destination": r.destination,
            "min_rate_usd": r.min_rate_usd,
            "equipment": list(r.equipment),
            "max_weight_lb": r.max_weight_lb,
            "account_group": r.account_group,
            "matched_24h": int(r.matched),
            "updated_at": iso(r.updated_at),
            "version": r.version,
        }
        for r in rows
    ]
    return page(tenant_id, items, None, len(items))


def _hour_cells(day: int, start: str, end: str) -> list[dict[str, int]]:
    """A window as whole-hour spans on the console's week grid (0 = Monday, as the engine counts).
    An overnight window (end <= start) runs to midnight and continues on the next day; partial hours
    are drawn as the whole hour they touch."""
    s = int(start[:2])
    e = int(end[:2]) + (1 if end[3:5] != "00" else 0)
    if e > s:
        return [{"day": day, "start_hour": s, "end_hour": e}]
    spans = [{"day": day, "start_hour": s, "end_hour": 24}]
    if e > 0:
        spans.append({"day": (day + 1) % 7, "start_hour": 0, "end_hour": e})
    return spans


async def schedules(conn: AsyncConnection, tenant_id: UUID) -> dict[str, Any]:
    rows = (
        await conn.execute(
            text(
                "SELECT id, name, timezone, windows, targets, enabled FROM schedules WHERE tenant_id = :t ORDER BY name"
            ),
            {"t": tenant_id},
        )
    ).all()
    items = []
    for r in rows:
        windows = [
            cell for w in r.windows for day in sorted(w["days"]) for cell in _hour_cells(day, w["start"], w["end"])
        ]
        items.append(
            {
                "tenant_id": str(tenant_id),
                "id": str(r.id),
                "name": r.name,
                "timezone": r.timezone,
                "targets": [str(x) for x in r.targets],
                "windows": windows,
                "enabled": r.enabled,
            }
        )
    return page(tenant_id, items, None, len(items))


# ---------------- audit and users ----------------


async def audit(conn: AsyncConnection, tenant_id: UUID, cursor: str | None, limit: int, redact: bool) -> dict[str, Any]:
    after = _decode_cursor(cursor)
    if after is not None and not after[1].isdigit():
        after = None  # a malformed cursor starts from the first page, like any other bad cursor
    rows = (
        await conn.execute(
            text(
                """SELECT id, at, actor, role, action, target, detail, ip_prefix FROM audit_log
                   WHERE tenant_id = :t AND (CAST(:at AS timestamptz) IS NULL OR (at, id) < (CAST(:at AS timestamptz), :key))
                   ORDER BY at DESC, id DESC LIMIT :n"""
            ),
            {"t": tenant_id, "at": after[0] if after else None, "key": int(after[1]) if after else 0, "n": limit + 1},
        )
    ).all()
    total = (
        await conn.execute(text("SELECT count(*) FROM audit_log WHERE tenant_id = :t"), {"t": tenant_id})
    ).scalar_one()
    more = len(rows) > limit
    rows = rows[:limit]
    items = [
        {
            "tenant_id": str(tenant_id),
            "id": str(r.id),
            "at": iso(r.at),
            "actor": mask_email(r.actor) if redact else r.actor,
            "role": r.role,
            "action": r.action,
            "target": r.target,
            "detail": r.detail,
            "ip": "hidden" if redact else (r.ip_prefix or ""),
        }
        for r in rows
    ]
    nxt = _encode_cursor(rows[-1].at, str(rows[-1].id)) if more and rows else None
    return page(tenant_id, items, nxt, int(total))


async def users(conn: AsyncConnection, tenant_id: UUID, redact: bool) -> dict[str, Any]:
    rows = (
        await conn.execute(
            text(
                "SELECT id, name, email, role, mfa_enabled, last_seen_at FROM users WHERE tenant_id = :t ORDER BY name"
            ),
            {"t": tenant_id},
        )
    ).all()
    items = [
        {
            "tenant_id": str(tenant_id),
            "id": str(r.id),
            "name": r.name,
            "email": mask_email(r.email) if redact else r.email,
            "role": r.role,
            "mfa": r.mfa_enabled,
            "last_seen_at": iso(r.last_seen_at),
        }
        for r in rows
    ]
    return page(tenant_id, items, None, len(items))


# ---------------- latency and overview ----------------


async def latency(conn: AsyncConnection, tenant_id: UUID, window_s: int) -> list[dict[str, Any]]:
    since = (await conn.execute(text("SELECT clock_timestamp()"))).scalar_one() - timedelta(seconds=window_s)
    return [
        {
            "key": LATENCY_KEYS[s.stage],
            "samples": s.samples,
            "p50": round(s.p50_ms or 0),
            "p95": round(s.p95_ms or 0),
            "p99": round(s.p99_ms or 0),
        }
        for s in await stage_latency(conn, tenant_id, since)
        if s.stage in LATENCY_KEYS
    ]


async def series(conn: AsyncConnection, tenant_id: UUID, minutes: int) -> dict[str, list[dict[str, Any]]]:
    rows = (
        await conn.execute(
            text(
                """SELECT m.minute,
                          count(c.id) AS total,
                          count(c.id) FILTER (WHERE c.state = 'CONFIRMED'
                                                OR c.resolution IN ('confirmed', 'confirmed_by_late_actor')) AS confirmed
                   FROM generate_series(date_trunc('minute', clock_timestamp()) - make_interval(mins => :m - 1),
                                        date_trunc('minute', clock_timestamp()), interval '1 minute') AS m(minute)
                   LEFT JOIN claims c ON c.tenant_id = :t AND date_trunc('minute', c.queued_at) = m.minute
                   GROUP BY m.minute ORDER BY m.minute"""
            ),
            {"t": tenant_id, "m": minutes},
        )
    ).all()
    return {
        "total": [{"t": iso(r.minute), "v": int(r.total)} for r in rows],
        "confirmed": [{"t": iso(r.minute), "v": int(r.confirmed)} for r in rows],
    }


async def cells(conn: AsyncConnection) -> list[dict[str, Any]]:
    """Cells and the tenants they run (directory tables, no tenant scope)."""
    rows = (
        await conn.execute(
            text(
                """SELECT c.id, c.name, c.region, c.capacity,
                          coalesce(array_agg(tc.tenant_id) FILTER (WHERE tc.tenant_id IS NOT NULL), '{}') AS tenants
                   FROM cells c LEFT JOIN tenant_cells tc ON tc.cell_id = c.id
                   WHERE c.enabled GROUP BY c.id ORDER BY c.id"""
            )
        )
    ).all()
    return [
        {"id": r.id, "name": r.name, "region": r.region, "capacity": r.capacity, "tenants": [str(t) for t in r.tenants]}
        for r in rows
    ]


async def workers_per_cell(conn: AsyncConnection, tenant_id: UUID, cfg: ApiSettings) -> dict[str, int]:
    """The tenant's live workers per cell (not stopped, heartbeat younger than the dead threshold)."""
    return {
        str(r.cell_id): int(r.n)
        for r in await conn.execute(
            text(
                """SELECT cell_id, count(*) AS n FROM workers
                   WHERE tenant_id = :t AND state <> 'stopped'
                     AND heartbeat_at > clock_timestamp() - make_interval(secs => :dead)
                   GROUP BY cell_id"""
            ),
            {"t": tenant_id, "dead": cfg.worker_dead_after_s},
        )
    }


async def overview(conn: AsyncConnection, tenant_id: UUID, cfg: ApiSettings) -> dict[str, Any]:
    by_state = {
        str(r.state): int(r.n)
        for r in await conn.execute(
            text(
                """SELECT state, count(*) AS n FROM claims
                   WHERE tenant_id = :t AND queued_at > clock_timestamp() - make_interval(mins => :m) GROUP BY 1"""
            ),
            {"t": tenant_id, "m": cfg.series_minutes},
        )
    }
    confirmed = (
        await conn.execute(
            text(
                """SELECT count(*) FROM claims
                   WHERE tenant_id = :t AND queued_at > clock_timestamp() - make_interval(mins => :m)
                     AND (state = 'CONFIRMED' OR resolution IN ('confirmed', 'confirmed_by_late_actor'))"""
            ),
            {"t": tenant_id, "m": cfg.series_minutes},
        )
    ).scalar_one()
    w = await workers(conn, tenant_id, cfg)
    a = await accounts(conn, tenant_id)
    stale = sum(x["status"] == "stale" for x in w["items"])
    attention = sum(x["session_state"] in ("expiring", "expired", "otp_required") for x in a["items"])
    unknown = by_state.get("UNKNOWN", 0)
    alerts = []
    if stale:
        alerts.append({"id": "stale-workers", "severity": "warning", "kind": "stale_workers", "count": stale})
    if attention:
        alerts.append({"id": "sessions", "severity": "warning", "kind": "sessions_need_attention", "count": attention})
    if unknown:
        alerts.append({"id": "unknown", "severity": "info", "kind": "claims_being_reconciled", "count": unknown})
    return {
        "tenant_id": str(tenant_id),
        "claims": {
            "window_s": cfg.series_minutes * 60,
            "total": sum(by_state.values()),
            "confirmed": int(confirmed),
            "finished": sum(by_state.get(s, 0) for s in ("CONFIRMED", "FAILED", "RECONCILED")),
            "by_state": by_state,
        },
        "series": await series(conn, tenant_id, cfg.series_minutes),
        "workers": {"total": len(w["items"]), "healthy": sum(x["status"] == "healthy" for x in w["items"])},
        "alerts": alerts,
    }
