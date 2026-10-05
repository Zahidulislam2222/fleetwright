"""Mock board persistence. All timestamps that matter for the latency report come from the database
clock (clock_timestamp()), never from a process clock."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from importlib import resources
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from mockboard.models import Adversity


async def apply_schema(engine: AsyncEngine) -> None:
    sql = resources.files("mockboard").joinpath("schema.sql").read_text(encoding="utf-8")
    async with engine.begin() as conn:
        # One transaction-scoped advisory lock so two board instances starting together do not race.
        await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext('mockboard-schema'))"))
        # Comments are dropped first: they may contain ";" and the file is split on ";".
        code = "\n".join(line for line in sql.splitlines() if not line.lstrip().startswith("--"))
        for statement in (part.strip() for part in code.split(";")):
            if statement:
                await conn.execute(text(statement))


async def ensure_settings(engine: AsyncEngine, initial: Adversity) -> None:
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO board_settings (id, value) VALUES (1, CAST(:v AS jsonb)) ON CONFLICT (id) DO NOTHING"),
            {"v": initial.model_dump_json()},
        )


async def get_settings(conn: AsyncConnection) -> Adversity:
    row = (await conn.execute(text("SELECT value FROM board_settings WHERE id = 1"))).one()
    return Adversity.model_validate(row.value)


async def put_settings(engine: AsyncEngine, value: Adversity, actor: str) -> Adversity:
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE board_settings SET value = CAST(:v AS jsonb), updated_at = clock_timestamp() WHERE id = 1"),
            {"v": value.model_dump_json()},
        )
        await admin_event(conn, "settings.update", {"by": actor, "value": value.model_dump(mode="json")})
    return value


async def admin_event(conn: AsyncConnection, kind: str, detail: dict[str, Any]) -> None:
    await conn.execute(
        text("INSERT INTO board_admin_events (kind, detail) VALUES (:k, CAST(:d AS jsonb))"),
        {"k": kind, "d": json.dumps(detail, default=str)},
    )


# ---------- accounts and login ----------


async def upsert_account(engine: AsyncEngine, username: str, email: str, password_hash: str) -> int:
    async with engine.begin() as conn:
        row = (
            await conn.execute(
                text(
                    """INSERT INTO board_accounts (username, email, password_hash) VALUES (:u, :e, :h)
                       ON CONFLICT (username) DO UPDATE SET email = EXCLUDED.email, password_hash = EXCLUDED.password_hash
                       RETURNING id"""
                ),
                {"u": username, "e": email, "h": password_hash},
            )
        ).one()
        await admin_event(conn, "account.upsert", {"username": username})
        return int(row.id)


async def find_account(conn: AsyncConnection, username: str) -> Any:
    return (
        await conn.execute(
            text("SELECT id, username, email, password_hash FROM board_accounts WHERE username = :u"), {"u": username}
        )
    ).one_or_none()


async def create_challenge(conn: AsyncConnection, token_hash: str, account_id: int, otp_hash: str, ttl_s: int) -> None:
    await conn.execute(
        text("DELETE FROM board_login_challenges WHERE account_id = :a OR expires_at < clock_timestamp()"),
        {"a": account_id},
    )
    await conn.execute(
        text(
            """INSERT INTO board_login_challenges (token_hash, account_id, otp_hash, expires_at)
               VALUES (:t, :a, :o, clock_timestamp() + make_interval(secs => :ttl))"""
        ),
        {"t": token_hash, "a": account_id, "o": otp_hash, "ttl": ttl_s},
    )


async def take_challenge_attempt(conn: AsyncConnection, token_hash: str) -> Any:
    """Counts one OTP attempt and returns the challenge, or None when it is unknown or expired."""
    return (
        await conn.execute(
            text(
                """UPDATE board_login_challenges SET attempts = attempts + 1
                   WHERE token_hash = :t AND expires_at > clock_timestamp()
                   RETURNING account_id, otp_hash, attempts"""
            ),
            {"t": token_hash},
        )
    ).one_or_none()


async def drop_challenge(conn: AsyncConnection, token_hash: str) -> None:
    await conn.execute(text("DELETE FROM board_login_challenges WHERE token_hash = :t"), {"t": token_hash})


async def create_session(
    conn: AsyncConnection, *, token_hash: str, account_id: int, csrf: str, ttl_s: int, single: bool
) -> datetime:
    if single:
        await conn.execute(
            text("UPDATE board_sessions SET revoked = true WHERE account_id = :a AND NOT revoked"), {"a": account_id}
        )
    row = (
        await conn.execute(
            text(
                """INSERT INTO board_sessions (token_hash, account_id, csrf, expires_at)
                   VALUES (:t, :a, :c, clock_timestamp() + make_interval(secs => :ttl)) RETURNING expires_at"""
            ),
            {"t": token_hash, "a": account_id, "c": csrf, "ttl": ttl_s},
        )
    ).one()
    return row.expires_at  # type: ignore[no-any-return]


@dataclass(frozen=True)
class SessionHit:
    account_id: int
    username: str
    csrf: str
    expires_at: datetime
    window_count: int
    minute_count: int
    captcha_question: str | None


async def touch_session(conn: AsyncConnection, token_hash: str, window_s: int) -> SessionHit | None:
    """Validates the session and counts the request in the captcha window and the per-minute window."""
    row = (
        await conn.execute(
            text(
                """UPDATE board_sessions s SET
                     window_start = CASE WHEN s.window_start < now() - make_interval(secs => :w) THEN now() ELSE s.window_start END,
                     window_count = CASE WHEN s.window_start < now() - make_interval(secs => :w) THEN 1 ELSE s.window_count + 1 END,
                     minute_start = CASE WHEN s.minute_start < now() - interval '1 minute' THEN now() ELSE s.minute_start END,
                     minute_count = CASE WHEN s.minute_start < now() - interval '1 minute' THEN 1 ELSE s.minute_count + 1 END
                   FROM board_accounts a
                   WHERE s.token_hash = :t AND NOT s.revoked AND s.expires_at > now() AND a.id = s.account_id
                   RETURNING s.account_id, a.username, s.csrf, s.expires_at, s.window_count, s.minute_count, s.captcha_answer"""
            ),
            {"t": token_hash, "w": window_s},
        )
    ).one_or_none()
    if row is None:
        return None
    return SessionHit(
        row.account_id, row.username, row.csrf, row.expires_at, row.window_count, row.minute_count, row.captcha_answer
    )


async def set_captcha(conn: AsyncConnection, token_hash: str, question: str) -> str:
    """Sets a captcha question unless one is already pending; returns the pending question."""
    row = (
        await conn.execute(
            text(
                """UPDATE board_sessions SET captcha_answer = COALESCE(captcha_answer, :q)
                   WHERE token_hash = :t RETURNING captcha_answer"""
            ),
            {"t": token_hash, "q": question},
        )
    ).one()
    return str(row.captcha_answer)


async def clear_captcha(conn: AsyncConnection, token_hash: str) -> None:
    await conn.execute(
        text(
            "UPDATE board_sessions SET captcha_answer = NULL, window_count = 0, window_start = now() WHERE token_hash = :t"
        ),
        {"t": token_hash},
    )


async def revoke_session(conn: AsyncConnection, token_hash: str) -> None:
    await conn.execute(text("UPDATE board_sessions SET revoked = true WHERE token_hash = :t"), {"t": token_hash})


async def expire_sessions(engine: AsyncEngine, username: str | None) -> int:
    async with engine.begin() as conn:
        result = await conn.execute(
            text(
                """UPDATE board_sessions s SET revoked = true FROM board_accounts a
                   WHERE a.id = s.account_id AND NOT s.revoked AND (CAST(:u AS text) IS NULL OR a.username = :u)"""
            ),
            {"u": username},
        )
        await admin_event(conn, "sessions.expire", {"username": username, "count": result.rowcount})
        return int(result.rowcount)


# ---------- loads ----------


async def insert_loads(conn: AsyncConnection, rows: list[dict[str, Any]]) -> list[Any]:
    if not rows:
        return []
    result = await conn.execute(
        text(
            """INSERT INTO loads (origin, destination, equipment, weight_lb, miles, rate_usd, pickup_at)
               SELECT r.origin, r.destination, r.equipment, r.weight_lb, r.miles, r.rate_usd, r.pickup_at
               FROM jsonb_to_recordset(CAST(:rows AS jsonb))
                 AS r(origin text, destination text, equipment text, weight_lb int, miles int, rate_usd int, pickup_at timestamptz)
               RETURNING id, ref, published_at"""
        ),
        {"rows": json.dumps(rows, default=str)},
    )
    return list(result.all())


async def list_loads(conn: AsyncConnection, after_id: int | None, visible_s: int, limit: int) -> list[Any]:
    if after_id is None:
        # First page: the newest loads, returned oldest-first like every later page.
        query = text(
            """SELECT * FROM (SELECT * FROM load_rows WHERE published_at > now() - make_interval(secs => :v)
               ORDER BY id DESC LIMIT :n) x ORDER BY id"""
        )
        params: dict[str, Any] = {"v": visible_s, "n": limit}
    else:
        query = text(
            """SELECT * FROM load_rows WHERE id > :after AND published_at > now() - make_interval(secs => :v)
               ORDER BY id LIMIT :n"""
        )
        params = {"after": after_id, "v": visible_s, "n": limit}
    return list((await conn.execute(query, params)).all())


@dataclass(frozen=True)
class BookResult:
    outcome: str  # booked | already_booked | not_found
    booked_at: datetime | None
    booked_by_self: bool


async def book(conn: AsyncConnection, ref: str, account_id: int, ack_lost: bool) -> BookResult:
    """First booker wins: the conditional UPDATE is atomic in Postgres. Every attempt is recorded."""
    won = (
        await conn.execute(
            text(
                """UPDATE loads SET booked_by = :a, booked_at = clock_timestamp()
                   WHERE ref = :r AND booked_by IS NULL AND booked_by_competitor IS NULL
                   RETURNING id, booked_at"""
            ),
            {"a": account_id, "r": ref},
        )
    ).one_or_none()
    if won is not None:
        outcome = "ack_lost" if ack_lost else "booked"
        await _attempt(conn, won.id, account_id, None, outcome)
        return BookResult("booked", won.booked_at, True)
    load = (
        await conn.execute(text("SELECT id, booked_by, booked_at FROM loads WHERE ref = :r"), {"r": ref})
    ).one_or_none()
    if load is None:
        return BookResult("not_found", None, False)
    await _attempt(conn, load.id, account_id, None, "already_booked")
    return BookResult("already_booked", load.booked_at, load.booked_by == account_id)


async def competitor_book(conn: AsyncConnection, load_id: int, name: str) -> bool:
    won = (
        await conn.execute(
            text(
                """UPDATE loads SET booked_by_competitor = :n, booked_at = clock_timestamp()
                   WHERE id = :i AND booked_by IS NULL AND booked_by_competitor IS NULL RETURNING id"""
            ),
            {"n": name, "i": load_id},
        )
    ).one_or_none()
    await _attempt(conn, load_id, None, name, "booked" if won else "already_booked")
    return won is not None


async def _attempt(
    conn: AsyncConnection, load_id: int, account_id: int | None, competitor: str | None, outcome: str
) -> None:
    await conn.execute(
        text("INSERT INTO booking_attempts (load_id, account_id, competitor, outcome) VALUES (:l, :a, :c, :o)"),
        {"l": load_id, "a": account_id, "c": competitor, "o": outcome},
    )


async def my_bookings(conn: AsyncConnection, account_id: int, limit: int) -> list[Any]:
    return list(
        (
            await conn.execute(
                text(
                    "SELECT ref, booked_at, rate_usd FROM loads WHERE booked_by = :a ORDER BY booked_at DESC LIMIT :n"
                ),
                {"a": account_id, "n": limit},
            )
        ).all()
    )


async def recent_public(conn: AsyncConnection, limit: int) -> list[Any]:
    return list(
        (
            await conn.execute(
                text("SELECT * FROM load_rows ORDER BY id DESC LIMIT :n"),
                {"n": limit},
            )
        ).all()
    )


# ---------- ground truth (admin) ----------


async def ground_truth(conn: AsyncConnection, since: datetime, limit: int) -> list[Any]:
    return list(
        (
            await conn.execute(
                text(
                    """SELECT l.*,
                          COALESCE((SELECT jsonb_agg(jsonb_build_object('at', b.at, 'outcome', b.outcome,
                                     'account', a2.username, 'competitor', b.competitor) ORDER BY b.at)
                                    FROM booking_attempts b LEFT JOIN board_accounts a2 ON a2.id = b.account_id
                                    WHERE b.load_id = l.id), '[]'::jsonb) AS attempts
                        FROM load_rows l WHERE l.published_at >= :s ORDER BY l.id LIMIT :n"""
                ),
                {"s": since, "n": limit},
            )
        ).all()
    )


async def duplicate_audit(conn: AsyncConnection, since: datetime) -> dict[str, Any]:
    """Duplicate action = more than one booking attempt on the same load by the fleet's accounts
    (any account, not counting rival bots). The board itself can never double-book."""
    rows = (
        await conn.execute(
            text(
                """SELECT l.ref, count(*) AS attempts, array_agg(a.username ORDER BY b.at) AS accounts
                   FROM booking_attempts b JOIN loads l ON l.id = b.load_id JOIN board_accounts a ON a.id = b.account_id
                   WHERE b.at >= :s GROUP BY l.ref HAVING count(*) > 1 ORDER BY l.ref LIMIT 1000"""
            ),
            {"s": since},
        )
    ).all()
    totals = (
        await conn.execute(
            text(
                """SELECT count(*) FILTER (WHERE account_id IS NOT NULL) AS fleet_attempts,
                          count(DISTINCT load_id) FILTER (WHERE account_id IS NOT NULL) AS fleet_loads,
                          count(*) FILTER (WHERE account_id IS NOT NULL AND outcome IN ('booked', 'ack_lost')) AS fleet_booked,
                          count(*) FILTER (WHERE competitor IS NOT NULL AND outcome = 'booked') AS competitor_booked
                   FROM booking_attempts WHERE at >= :s"""
            ),
            {"s": since},
        )
    ).one()
    published = (
        await conn.execute(text("SELECT count(*) AS n FROM loads WHERE published_at >= :s"), {"s": since})
    ).one()
    return {
        "since": since,
        "loads_published": published.n,
        "fleet_attempts": totals.fleet_attempts,
        "fleet_loads_attempted": totals.fleet_loads,
        "fleet_booked": totals.fleet_booked,
        "competitor_booked": totals.competitor_booked,
        "duplicate_loads": [{"ref": r.ref, "attempts": r.attempts, "accounts": list(r.accounts)} for r in rows],
    }


async def reset_data(engine: AsyncEngine) -> None:
    async with engine.begin() as conn:
        await conn.execute(text("TRUNCATE booking_attempts, loads RESTART IDENTITY"))
        await admin_event(conn, "data.reset", {})


async def db_now(conn: AsyncConnection) -> datetime:
    return (await conn.execute(text("SELECT clock_timestamp() AS db_time"))).one().db_time  # type: ignore[no-any-return]
