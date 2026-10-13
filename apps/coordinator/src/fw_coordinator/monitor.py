"""Bounded HTTP monitoring with durable failure/recovery notifications.

Run on the server for authenticated workflow metrics and archive age. Run independently on an
operator machine for external HTTPS availability. No SaaS, message recipient or paid API is used.
Only safe error categories and fixed metric values are persisted; URLs, headers and bodies are not.
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import json
import math
import os
import re
import sqlite3
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import httpx

from fw_core.settings import MonitorAppSettings, MonitorSettings, ProbeSettings, load

from .monitor_grant import issue


@dataclass(frozen=True)
class Observation:
    healthy: bool
    elapsed_ms: float
    reason: str
    metrics: dict[str, float] = field(default_factory=dict)


# These names/states are the bounded metric protocol emitted by workflow_health.prometheus().
METRIC_NAME = re.compile(
    r"^(fleetwright_(?:workflow_alerts|freight_unknown|outbox_pending)|"
    r'fleetwright_workflow_jobs\{state="(?:PENDING|QUEUED|LEASED|ACTING|CONFIRMED|FAILED|UNKNOWN|CANCELLED)"\})$'
)


class ObservationGrant:
    """Renew an observe-only credential transactionally; only its private recovery file holds it."""

    def __init__(self, cfg: MonitorAppSettings) -> None:
        self.cfg = cfg
        self.token: str | None = None
        self.identifier: UUID | None = None
        self.renew_at = 0.0
        grant = cfg.monitor_grant
        if grant is not None and grant.token_file.exists():
            if grant.token_file.is_symlink() or grant.token_file.stat().st_size > 8192:
                raise ValueError("unsafe observation grant recovery file")
            previous = json.loads(grant.token_file.read_bytes())
            if previous.get("tenant_id") != str(grant.tenant_id):
                raise ValueError("observation grant tenant changed")
            self.identifier = UUID(previous["grant_id"])

    async def ensure(self) -> None:
        grant = self.cfg.monitor_grant
        if grant is None or time.monotonic() < self.renew_at:
            return
        if grant.authority_command is not None:
            request = grant.model_dump(mode="json") | {
                "predecessor": str(self.identifier) if self.identifier else None,
            }
            process = await asyncio.create_subprocess_exec(
                *grant.authority_command,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _stderr = await asyncio.wait_for(
                    process.communicate(json.dumps(request).encode()), self.cfg.monitor.timeout_s
                )
            except TimeoutError:
                process.kill()
                await process.communicate()
                raise RuntimeError("observation grant authority timeout") from None
            if process.returncode or len(stdout) > 8192:
                raise ValueError("observation grant authority failed")
            result = json.loads(stdout)
        else:
            if self.cfg.app_db is None:
                raise ValueError("missing observation grant authority")
            result = await issue(self.cfg.app_db, grant, self.identifier)
        if not isinstance(result, dict) or set(result) != {"grant_id", "token", "tenant_id"}:
            raise ValueError("invalid observation grant response")
        identifier = UUID(result["grant_id"])
        token = result["token"]
        if (
            result["tenant_id"] != str(grant.tenant_id)
            or not isinstance(token, str)
            or not re.fullmatch(r"[A-Za-z0-9_-]{32,128}", token)
        ):
            raise ValueError("invalid observation grant credential")
        grant.token_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        temporary = grant.token_file.with_name(grant.token_file.name + "." + uuid4().hex + ".tmp")
        descriptor = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as output:
            json.dump(result, output)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, grant.token_file)
        self.identifier, self.token = identifier, token
        self.renew_at = time.monotonic() + grant.ttl_s - grant.renewal_margin_s
        for probe in self.cfg.monitor.probes:
            if probe.bearer_token is not None:
                probe.bearer_token = type(probe.bearer_token)(token)
                probe.tenant_id = str(grant.tenant_id)


def parse_metrics(body: bytes) -> dict[str, float]:
    metrics = {}
    for line in body.decode("utf-8").splitlines():
        if not line or line.startswith("#"):
            continue
        parts = line.split()
        if not parts:
            continue
        if not METRIC_NAME.fullmatch(parts[0]):
            continue
        if len(parts) != 2 or parts[0] in metrics:
            raise ValueError("invalid metric structure")
        value = float(parts[1])
        if not math.isfinite(value) or value < 0:
            raise ValueError("invalid metric value")
        metrics[parts[0]] = value
    if "fleetwright_workflow_alerts" not in metrics:
        raise ValueError("missing alert metric")
    return metrics


def database(cfg: MonitorSettings) -> sqlite3.Connection:
    cfg.database.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    if cfg.database.is_symlink():
        raise ValueError("monitor database must not be a symlink")
    conn = sqlite3.connect(cfg.database)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS checks (
            id INTEGER PRIMARY KEY, at REAL NOT NULL, name TEXT NOT NULL,
            healthy INTEGER NOT NULL, latency_ms REAL NOT NULL, reason TEXT NOT NULL);
        CREATE INDEX IF NOT EXISTS checks_name_at ON checks(name, at);
        CREATE TABLE IF NOT EXISTS state (
            name TEXT PRIMARY KEY, failures INTEGER NOT NULL, alerted INTEGER NOT NULL);
        CREATE TABLE IF NOT EXISTS notifications (
            id INTEGER PRIMARY KEY, at REAL NOT NULL, name TEXT NOT NULL, kind TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS metrics (
            at REAL NOT NULL, probe TEXT NOT NULL, name TEXT NOT NULL, value REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS metrics_probe_at ON metrics(probe, at);
    """)
    if os.name == "posix":
        cfg.database.chmod(0o600)
    return conn


def record(
    cfg: MonitorSettings,
    conn: sqlite3.Connection,
    name: str,
    healthy: bool,
    elapsed: float,
    reason: str,
    metrics: dict[str, float] | None = None,
) -> None:
    now = time.time()
    with conn:
        previous = conn.execute("SELECT failures,alerted FROM state WHERE name=?", (name,)).fetchone() or (0, 0)
        failures = 0 if healthy else previous[0] + 1
        alerted = failures >= cfg.failures_before_alert
        conn.execute(
            "INSERT INTO checks(at,name,healthy,latency_ms,reason) VALUES(?,?,?,?,?)",
            (now, name, healthy, elapsed, reason),
        )
        conn.execute("INSERT OR REPLACE INTO state VALUES(?,?,?)", (name, failures, alerted))
        if metrics:
            conn.executemany(
                "INSERT INTO metrics VALUES(?,?,?,?)", ((now, name, key, value) for key, value in metrics.items())
            )
        if alerted != bool(previous[1]):
            conn.execute(
                "INSERT INTO notifications(at,name,kind) VALUES(?,?,?)",
                (now, name, "recovered" if healthy else "failed"),
            )
        cutoff = now - cfg.retention_days * 24 * 60 * 60
        conn.execute("DELETE FROM checks WHERE at<?", (cutoff,))
        conn.execute("DELETE FROM notifications WHERE at<?", (cutoff,))
        conn.execute("DELETE FROM metrics WHERE at<?", (cutoff,))
    # This file is an idempotent local notification sink, regenerated from committed records.
    # A crash after the transaction cannot lose an alert; the next cycle writes it again.
    notices = conn.execute(
        "SELECT id,at,name,kind FROM notifications ORDER BY id DESC LIMIT ?", (cfg.notification_limit,)
    ).fetchall()
    cfg.notification_file.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    tmp = cfg.notification_file.with_name(cfg.notification_file.name + "." + uuid4().hex + ".tmp")
    descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as output:
        json.dump([dict(zip(("id", "at", "name", "kind"), row, strict=True)) for row in notices], output)
        output.flush()
        os.fsync(output.fileno())
    os.replace(tmp, cfg.notification_file)


async def check(client: httpx.AsyncClient, cfg: MonitorSettings, probe: ProbeSettings) -> Observation:
    started = time.monotonic()

    def observation(healthy: bool, reason: str, metrics: dict[str, float] | None = None) -> Observation:
        return Observation(healthy, (time.monotonic() - started) * 1000, reason, metrics or {})

    headers = {}
    if probe.bearer_token is not None:
        headers["Authorization"] = "Bearer " + probe.bearer_token.get_secret_value()
    if probe.tenant_id:
        headers["X-Fleetwright-Tenant"] = probe.tenant_id
    try:
        async with asyncio.timeout(cfg.timeout_s), client.stream("GET", probe.url, headers=headers) as response:
            if response.status_code != probe.expected_status:
                return observation(False, "http_status")
            body = bytearray()
            async for chunk in response.aiter_bytes():
                if len(chunk) > cfg.response_max_bytes - len(body):
                    return observation(False, "response_limit")
                body.extend(chunk)
            if probe.bearer_token is not None:
                try:
                    metrics = parse_metrics(bytes(body))
                except (UnicodeError, ValueError):
                    return observation(False, "invalid_metrics")
                if metrics["fleetwright_workflow_alerts"] > 0:
                    return observation(False, "workflow_alert", metrics)
                return observation(True, "healthy", metrics)
        return observation(True, "healthy")
    except (httpx.HTTPError, UnicodeError, ValueError, TimeoutError):
        return observation(False, "transport_or_format")


def archive_fresh(cfg: MonitorSettings) -> bool:
    if cfg.backup_directory is None:
        return True
    candidates = [
        p
        for p in cfg.backup_directory.glob("*/manifest.json")
        if not p.is_symlink() and not p.parent.is_symlink() and p.is_file()
    ]
    return bool(candidates) and time.time() - max(p.stat().st_mtime for p in candidates) <= cfg.backup_max_age_s


async def cycle(cfg: MonitorSettings, conn: sqlite3.Connection, client: httpx.AsyncClient) -> None:
    for probe in cfg.probes:
        result = await check(client, cfg, probe)
        record(cfg, conn, probe.name, result.healthy, result.elapsed_ms, result.reason, result.metrics)
    if cfg.backup_directory is not None:
        fresh = archive_fresh(cfg)
        record(cfg, conn, "backup_freshness", fresh, 0, "healthy" if fresh else "stale_archive")


def report(cfg: MonitorSettings, conn: sqlite3.Connection) -> dict[str, Any]:
    rows = conn.execute("SELECT name,count(*),sum(healthy),min(at),max(at) FROM checks GROUP BY name").fetchall()
    metrics: dict[str, dict[str, float]] = {}
    for probe, name, value in conn.execute(
        "SELECT m.probe,m.name,m.value FROM metrics m JOIN "
        "(SELECT probe,max(at) AS at FROM metrics GROUP BY probe) latest "
        "ON m.probe=latest.probe AND m.at=latest.at"
    ):
        metrics.setdefault(probe, {})[name] = value
    return {
        "probes": [
            {
                "name": row[0],
                "samples": row[1],
                "healthy_samples": row[2],
                "first_sample": row[3],
                "last_sample": row[4],
            }
            for row in rows
        ],
        "failures": conn.execute("SELECT count(*) FROM state WHERE alerted=1").fetchone()[0],
        "interval_s": cfg.interval_s,
        "latest_metrics": metrics,
        "latest_checks": [
            dict(zip(("name", "healthy", "latency_ms", "reason", "at"), row, strict=True))
            for row in conn.execute(
                "SELECT c.name,c.healthy,c.latency_ms,c.reason,c.at FROM checks c JOIN "
                "(SELECT name,max(id) AS id FROM checks GROUP BY name) latest ON c.id=latest.id"
            )
        ],
        "notifications": [
            dict(zip(("at", "name", "kind"), row, strict=True))
            for row in conn.execute(
                "SELECT at,name,kind FROM notifications ORDER BY id DESC LIMIT ?", (cfg.notification_limit,)
            )
        ],
    }


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=("once", "loop", "report"))
    parser.add_argument("--settings-file", type=Path)
    args = parser.parse_args()
    app_cfg = (
        MonitorAppSettings(_env_file=None, **json.loads(args.settings_file.read_text(encoding="utf-8")))
        if args.settings_file
        else load(MonitorAppSettings)
    )
    cfg = app_cfg.monitor
    if os.name == "posix":
        os.umask(0o077)
    with contextlib.closing(database(cfg)) as conn:
        if args.operation == "report":
            print(json.dumps(report(cfg, conn)))
            return
        grant = ObservationGrant(app_cfg)
        latest_notice: tuple[int, float] | None = None
        async with httpx.AsyncClient(timeout=cfg.timeout_s, follow_redirects=False, trust_env=False) as client:
            while True:
                first_id = conn.execute("SELECT coalesce(max(id),0) FROM checks").fetchone()[0]
                if app_cfg.monitor_grant is not None:
                    try:
                        await grant.ensure()
                    except Exception:
                        # Keep health/backup probes running; never log bearer/DSN/exception text.
                        record(cfg, conn, "observation_grant", False, 0, "grant_authority")
                    else:
                        record(cfg, conn, "observation_grant", True, 0, "healthy")
                await cycle(cfg, conn, client)
                if args.operation == "once":
                    print(json.dumps(report(cfg, conn)))
                    if conn.execute("SELECT count(*) FROM checks WHERE id>? AND healthy=0", (first_id,)).fetchone()[0]:
                        raise SystemExit(1)
                    return
                # Retention can delete every row and SQLite may reuse its numeric ID. Bind the
                # journal cursor to event time as well so a new probe's alert remains visible.
                notice = conn.execute("SELECT id,at FROM notifications ORDER BY id DESC LIMIT 1").fetchone()
                if notice != latest_notice:
                    # Human-facing local terminal/journal surface, backed by the private durable sink.
                    print(json.dumps(report(cfg, conn)), flush=True)
                    latest_notice = notice
                await asyncio.sleep(cfg.interval_s)


if __name__ == "__main__":
    asyncio.run(main())
