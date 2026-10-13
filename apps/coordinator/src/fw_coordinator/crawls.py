"""Durable tenant-scoped crawler. PostgreSQL is the authoritative frontier and lease clock.

One bounded page transaction at a time permits restart without losing completed pages. Only a
successful complete cycle classifies removals. Fences stop an expired worker committing output.
"""

from __future__ import annotations

import asyncio
import base64
import contextlib
import hashlib
import http.client
import json
import logging
import os
import secrets
import sys
from typing import Any
from urllib.parse import urljoin
from urllib.robotparser import RobotFileParser
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from fw_coordinator.crawl_contracts import Definition, definitions, extract
from fw_coordinator.crawl_http import EgressDenied, Response
from fw_core.db import make_engine, system_tx, tenant_tx
from fw_core.settings import CrawlAppSettings, load

log = logging.getLogger(__name__)


class OriginBusy(Exception):
    """No request sent; retry admission without consuming a destination-error attempt."""


async def submit(conn: AsyncConnection, tenant: UUID, name: str, contract: Definition, max_pages: int) -> UUID:
    if len(set(contract.seeds)) > max_pages:
        raise ValueError("seed count exceeds the configured page budget")
    # Serializing submissions for a tenant/definition prevents simultaneous cycles comparing
    # against each other's partial extraction state.
    await conn.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {"key": str(tenant) + name})
    existing = await conn.scalar(
        text(
            "SELECT id FROM crawl_jobs WHERE tenant_id=:t AND definition=:d AND state IN ('QUEUED','RUNNING') LIMIT 1"
        ),
        {"t": tenant, "d": name},
    )
    if existing:
        raise ValueError("a cycle is already active for this definition")
    job = uuid4()
    await conn.execute(
        text(
            "INSERT INTO crawl_jobs(tenant_id,id,definition,contract_hash,contract,state) "
            "VALUES(:t,:j,:d,:h,CAST(:c AS jsonb),'QUEUED')"
        ),
        {"t": tenant, "j": job, "d": name, "h": contract.fingerprint(), "c": contract.model_dump_json()},
    )
    for path in contract.seeds:
        await conn.execute(
            text("INSERT INTO crawl_frontier(tenant_id,job_id,path) VALUES(:t,:j,:p) ON CONFLICT DO NOTHING"),
            {"t": tenant, "j": job, "p": path},
        )
    return job


class Crawler:
    def __init__(self, cfg: CrawlAppSettings, engine: AsyncEngine) -> None:
        self.cfg, self.engine = cfg, engine
        self._robots: dict[UUID, RobotFileParser | None] = {}

    def origin(self, name: str) -> str:
        if name == "owned_board":
            return self.cfg.board_client.internal_url.rstrip("/")
        value = self.cfg.crawl.origins.get(name)
        if value is None:
            raise EgressDenied("crawl origin is not configured")
        return value.rstrip("/")

    async def request(self, path: str, origin_name: str) -> Response:
        cfg = self.cfg.crawl
        origin = self.origin(origin_name)
        origin_hash = hashlib.sha256(origin.encode()).hexdigest()
        async with system_tx(self.engine) as conn:
            await conn.execute(
                text(
                    "INSERT INTO crawl_domains(origin_hash,next_at) VALUES(:h,clock_timestamp()) ON CONFLICT DO NOTHING"
                ),
                {"h": origin_hash},
            )
            admitted = await conn.scalar(
                text(
                    "UPDATE crawl_domains SET next_at=clock_timestamp()+make_interval(secs=>:delay) "
                    "WHERE origin_hash=:h AND next_at<=clock_timestamp() RETURNING origin_hash"
                ),
                {"h": origin_hash, "delay": cfg.domain_delay_s},
            )
        if not admitted:
            raise OriginBusy
        payload = json.dumps(
            {
                "url": urljoin(origin + "/", path),
                "origin": origin,
                "allow_private": origin_name == "owned_board" and cfg.owned_origin_private_access,
                "timeout": cfg.timeout_s,
                "limit": cfg.max_response_bytes,
                "user_agent": cfg.user_agent,
            }
        ).encode()
        process = await asyncio.create_subprocess_exec(
            sys.executable,
            "-m",
            "fw_coordinator.crawl_fetch",
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        try:
            stdout, _ = await asyncio.wait_for(process.communicate(payload), cfg.request_budget_s)
            if process.returncode:
                raise ValueError("destination request failed")
            value = json.loads(stdout)
            body = base64.b64decode(value["body"], validate=True)
            if len(body) > cfg.max_response_bytes:
                raise ValueError("destination response exceeds configured limit")
            return Response(int(value["status"]), body, str(value["content_type"]))
        finally:
            if process.returncode is None:
                process.kill()
                await process.wait()

    async def lease(self, tenant: UUID) -> dict[str, Any] | None:
        async with tenant_tx(self.engine, tenant) as conn:
            row = (
                (
                    await conn.execute(
                        text("""
                UPDATE crawl_jobs SET state='RUNNING', fence=nextval('crawl_fence'),
                  lease_until=clock_timestamp()+make_interval(secs=>:lease)
                WHERE tenant_id=:t AND id=(SELECT id FROM crawl_jobs
                  WHERE tenant_id=:t AND (state='QUEUED' OR (state='RUNNING' AND lease_until<clock_timestamp()))
                  ORDER BY created_at LIMIT 1 FOR UPDATE SKIP LOCKED) RETURNING *
            """),
                        {"t": tenant, "lease": self.cfg.crawl.lease_s},
                    )
                )
                .mappings()
                .one_or_none()
            )
            return dict(row) if row else None

    async def owns(self, conn: AsyncConnection, tenant: UUID, job: UUID, fence: int) -> bool:
        return bool(
            await conn.scalar(
                text(
                    "SELECT id FROM crawl_jobs WHERE tenant_id=:t AND id=:j "
                    "AND fence=:f AND state='RUNNING' AND lease_until>clock_timestamp() "
                    "AND EXISTS(SELECT 1 FROM tenant_cells WHERE tenant_id=:t AND cell_id=:cell) FOR UPDATE"
                ),
                {"t": tenant, "j": job, "f": fence, "cell": self.cfg.crawl.cell},
            )
        )

    async def page(self, tenant: UUID, job: dict[str, Any]) -> bool:
        key, fence = job["id"], job["fence"]
        cfg = self.cfg.crawl
        contract = Definition.model_validate(job["contract"])
        async with tenant_tx(self.engine, tenant) as conn:
            if not await self.owns(conn, tenant, key, fence):
                return False
            cancelled = await conn.scalar(
                text("SELECT cancel_requested FROM crawl_jobs WHERE tenant_id=:t AND id=:j"), {"t": tenant, "j": key}
            )
            if cancelled:
                await conn.execute(
                    text(
                        "UPDATE crawl_jobs SET state='CANCELLED',completed_at=clock_timestamp() WHERE tenant_id=:t AND id=:j"
                    ),
                    {"t": tenant, "j": key},
                )
                return False
            frontier = (
                await conn.execute(
                    text(
                        "SELECT path,attempts FROM crawl_frontier WHERE tenant_id=:t AND job_id=:j "
                        "AND NOT done AND attempts<:max ORDER BY due_at,path LIMIT 1"
                    ),
                    {"t": tenant, "j": key, "max": cfg.max_attempts},
                )
            ).one_or_none()
            if frontier is None:
                return False
            due = await conn.scalar(
                text(
                    "SELECT due_at<=clock_timestamp() FROM crawl_frontier WHERE tenant_id=:t AND job_id=:j AND path=:p"
                ),
                {"t": tenant, "j": key, "p": frontier.path},
            )
            if not due:
                return True
            await conn.execute(
                text(
                    "UPDATE crawl_jobs SET lease_until=clock_timestamp()+make_interval(secs=>:lease) WHERE tenant_id=:t AND id=:j"
                ),
                {"t": tenant, "j": key, "lease": cfg.lease_s},
            )
        try:
            if contract.fingerprint() != job["contract_hash"]:
                raise ValueError("contract changed")
            if contract.respect_robots:
                if key not in self._robots:
                    robots = await self.request("/robots.txt", contract.origin)
                    if robots.status not in (200, 404):
                        raise ValueError("robots unavailable")
                    policy = RobotFileParser()
                    policy.parse(robots.body.decode("utf-8").splitlines())
                    self._robots[key] = policy if robots.status == 200 else None
                cached_policy = self._robots[key]
                if cached_policy is not None and not cached_policy.can_fetch(cfg.user_agent, frontier.path):
                    raise EgressDenied("robots denied")
            response = await self.request(frontier.path, contract.origin)
            if response.status != 200:
                raise ValueError("destination response failure")
            items, links = extract(contract, response.body, cfg.max_items_per_page)
        except OriginBusy:
            return True
        except (OSError, TimeoutError, ValueError, KeyError, IndexError, TypeError, http.client.HTTPException):
            async with tenant_tx(self.engine, tenant) as conn:
                if await self.owns(conn, tenant, key, fence):
                    # Milliseconds per second is a unit conversion, not a retry policy default.
                    jitter = secrets.randbelow(max(1, round(cfg.retry_jitter_s * 1000))) / 1000
                    delay = cfg.retry_base_s * (2**frontier.attempts) + jitter
                    await conn.execute(
                        text(
                            "UPDATE crawl_frontier SET attempts=attempts+1,due_at=clock_timestamp()+make_interval(secs=>:delay) "
                            "WHERE tenant_id=:t AND job_id=:j AND path=:p"
                        ),
                        {"t": tenant, "j": key, "p": frontier.path, "delay": delay},
                    )
                    await conn.execute(
                        text("UPDATE crawl_jobs SET errors=errors+1 WHERE tenant_id=:t AND id=:j"),
                        {"t": tenant, "j": key},
                    )
            return True
        async with tenant_tx(self.engine, tenant) as conn:
            if not await self.owns(conn, tenant, key, fence):
                return False
            added, changed, duplicate = 0, 0, 0
            for item in items:
                identity = str(item[contract.identity_field])
                digest = hashlib.sha256(json.dumps(item, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
                previous = (
                    await conn.execute(
                        text(
                            "SELECT content_hash,seen_job FROM crawl_items WHERE tenant_id=:t AND definition=:d AND identity=:i"
                        ),
                        {"t": tenant, "d": job["definition"], "i": identity},
                    )
                ).one_or_none()
                added += previous is None
                changed += previous is not None and previous.content_hash != digest
                duplicate += previous is not None and previous.seen_job == key
                await conn.execute(
                    text("""INSERT INTO crawl_items(tenant_id,definition,identity,content_hash,data,seen_job)
                    VALUES(:t,:d,:i,:h,CAST(:data AS jsonb),:j) ON CONFLICT(tenant_id,definition,identity)
                    DO UPDATE SET content_hash=excluded.content_hash,data=excluded.data,
                      seen_job=excluded.seen_job,updated_at=clock_timestamp()"""),
                    {
                        "t": tenant,
                        "d": job["definition"],
                        "i": identity,
                        "h": digest,
                        "data": json.dumps(item),
                        "j": key,
                    },
                )
            count = await conn.scalar(
                text("SELECT count(*) FROM crawl_frontier WHERE tenant_id=:t AND job_id=:j"), {"t": tenant, "j": key}
            )
            for link in links:
                exists = await conn.scalar(
                    text("SELECT path FROM crawl_frontier WHERE tenant_id=:t AND job_id=:j AND path=:p"),
                    {"t": tenant, "j": key, "p": link},
                )
                if exists is not None:
                    continue
                if count >= cfg.max_pages:
                    await conn.execute(
                        text(
                            "UPDATE crawl_jobs SET alerts=alerts || '[\"page_limit\"]'::jsonb WHERE tenant_id=:t AND id=:j"
                        ),
                        {"t": tenant, "j": key},
                    )
                    break
                inserted = await conn.execute(
                    text("INSERT INTO crawl_frontier(tenant_id,job_id,path) VALUES(:t,:j,:p) ON CONFLICT DO NOTHING"),
                    {"t": tenant, "j": key, "p": link},
                )
                count += inserted.rowcount
            await conn.execute(
                text("UPDATE crawl_frontier SET done=true WHERE tenant_id=:t AND job_id=:j AND path=:p"),
                {"t": tenant, "j": key, "p": frontier.path},
            )
            await conn.execute(
                text(
                    "UPDATE crawl_jobs SET pages=pages+1,items=items+:items,added=added+:added,changed=changed+:changed,"
                    "alerts=alerts || CAST(:alerts AS jsonb) WHERE tenant_id=:t AND id=:j"
                ),
                {
                    "t": tenant,
                    "j": key,
                    "items": len(items),
                    "added": added,
                    "changed": changed,
                    "alerts": json.dumps(["duplicate_items"] if duplicate else []),
                },
            )
        return True

    async def finish(self, tenant: UUID, job: dict[str, Any]) -> None:
        key = job["id"]
        cfg = self.cfg.crawl
        folder = cfg.output_directory / str(tenant)
        folder.mkdir(parents=True, exist_ok=True, mode=0o700)
        artifact = str(key) + ".jsonl"
        tmp = folder / (str(key) + ".tmp")
        async with tenant_tx(self.engine, tenant) as conn:
            if not await self.owns(conn, tenant, key, job["fence"]):
                return
            current = (
                (
                    await conn.execute(
                        text("SELECT * FROM crawl_jobs WHERE tenant_id=:t AND id=:j"), {"t": tenant, "j": key}
                    )
                )
                .mappings()
                .one()
            )
            dead = await conn.scalar(
                text("SELECT count(*) FROM crawl_frontier WHERE tenant_id=:t AND job_id=:j AND NOT done"),
                {"t": tenant, "j": key},
            )
            alerts = list(current["alerts"])
            previous = await conn.scalar(
                text(
                    "SELECT items FROM crawl_jobs WHERE tenant_id=:t AND definition=:d AND state='COMPLETE' "
                    "ORDER BY completed_at DESC LIMIT 1"
                ),
                {"t": tenant, "d": job["definition"]},
            )
            if current["items"] == 0:
                alerts.append("zero_results")
            if previous and current["items"] < previous * (1 - cfg.drop_alert_share):
                alerts.append("result_drop")
            complete = not dead and not {"page_limit", "zero_results", "result_drop"}.intersection(alerts)
            removed = 0
            if complete:
                removed = (
                    await conn.execute(
                        text("DELETE FROM crawl_items WHERE tenant_id=:t AND definition=:d AND seen_job<>:j"),
                        {"t": tenant, "d": job["definition"], "j": key},
                    )
                ).rowcount
            descriptor = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as output:
                cursor = await conn.stream(
                    text(
                        "SELECT data FROM crawl_items WHERE tenant_id=:t AND definition=:d AND seen_job=:j ORDER BY identity"
                    ),
                    {"t": tenant, "d": job["definition"], "j": key},
                )
                async for row in cursor:
                    output.write(json.dumps(row.data, sort_keys=True) + "\n")
                output.flush()
                os.fsync(output.fileno())
            os.replace(tmp, folder / artifact)
            await conn.execute(
                text(
                    "UPDATE crawl_jobs SET state=:state,completed_at=clock_timestamp(),alerts=CAST(:alerts AS jsonb),"
                    "removed=:removed,artifact=:artifact WHERE tenant_id=:t AND id=:j"
                ),
                {
                    "t": tenant,
                    "j": key,
                    "state": "COMPLETE" if complete else "FAILED",
                    "alerts": json.dumps(sorted(set(alerts))),
                    "removed": removed,
                    "artifact": artifact,
                },
            )
            await conn.execute(
                text(
                    "DELETE FROM crawl_items WHERE tenant_id=:t AND updated_at<clock_timestamp()-make_interval(days=>:days)"
                ),
                {"t": tenant, "days": cfg.retention_days},
            )
        await self.retention(tenant)

    async def retention(self, tenant: UUID) -> None:
        cfg = self.cfg.crawl
        async with tenant_tx(self.engine, tenant) as conn:
            await conn.execute(
                text(
                    "DELETE FROM crawl_items WHERE tenant_id=:t AND updated_at<clock_timestamp()-make_interval(days=>:days)"
                ),
                {"t": tenant, "days": cfg.retention_days},
            )
            rows = (
                await conn.execute(
                    text(
                        "SELECT id FROM crawl_jobs WHERE tenant_id=:t "
                        "AND artifact IS NOT NULL AND completed_at<clock_timestamp()-make_interval(days=>:days) "
                        "ORDER BY completed_at LIMIT :batch"
                    ),
                    {"t": tenant, "days": cfg.retention_days, "batch": cfg.retention_batch},
                )
            ).all()
            for row in rows:
                artifact = cfg.output_directory / str(tenant) / (str(row.id) + ".jsonl")
                if artifact.is_file() and not artifact.is_symlink():
                    artifact.unlink()
                await conn.execute(
                    text("DELETE FROM crawl_frontier WHERE tenant_id=:t AND job_id=:j"), {"t": tenant, "j": row.id}
                )
                await conn.execute(
                    text("UPDATE crawl_jobs SET artifact=NULL WHERE tenant_id=:t AND id=:j"), {"t": tenant, "j": row.id}
                )

    async def run_job(self, tenant: UUID, job: dict[str, Any]) -> None:
        stopping = asyncio.Event()
        try:
            while await self.page(tenant, job):
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stopping.wait(), self.cfg.crawl.poll_s)
            await self.finish(tenant, job)
        finally:
            self._robots.pop(job["id"], None)

    async def run(self) -> None:
        cursor: UUID | None = None
        while True:
            async with system_tx(self.engine) as conn:
                rows = (
                    await conn.execute(
                        text(
                            "SELECT tenant_id FROM tenant_cells WHERE cell_id=:cell "
                            "AND (CAST(:cursor AS uuid) IS NULL OR tenant_id>CAST(:cursor AS uuid)) ORDER BY tenant_id LIMIT :batch"
                        ),
                        {"cell": self.cfg.crawl.cell, "cursor": cursor, "batch": self.cfg.crawl.tenant_batch},
                    )
                ).all()
            for row in rows:
                if job := await self.lease(row.tenant_id):
                    await self.run_job(row.tenant_id, job)
                await self.retention(row.tenant_id)
            cursor = rows[-1].tenant_id if rows else None
            await asyncio.sleep(self.cfg.crawl.poll_s)


async def main() -> None:
    cfg = load(CrawlAppSettings)
    definitions(cfg.config_dir)  # fail startup on invalid maintained contracts
    engine = make_engine(cfg.app_db.dsn, cfg.app_db, "crawler")
    try:
        await Crawler(cfg, engine).run()
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
