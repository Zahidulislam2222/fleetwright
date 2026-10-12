"""Durable workflow runner, independent of the freight watcher/dispatcher.

Run more than one process safely. Restarting performs DB-clock recovery and reconciliation;
UNKNOWN jobs are never selected for execution. Polling is intentional: Postgres is the durable
dispatch authority, so a notification lost during a crash cannot strand a submitted job.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from playwright.async_api import Browser, async_playwright
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from fw_browser.otp import MailpitOtp
from fw_browser.workflows import BrowserWorkflow
from fw_core import workflows as jobs
from fw_core.crypto import Envelope
from fw_core.db import make_engine, system_tx, tenant_tx
from fw_core.settings import WorkflowAppSettings, load
from fw_core.targets import load_targets
from fw_core.vault import Account, Vault
from fw_core.workflow_contracts import load_workflows

log = logging.getLogger(__name__)


@dataclass
class Runner:
    cfg: WorkflowAppSettings
    engine: AsyncEngine
    browser: Browser
    otp: MailpitOtp
    worker_id: str

    async def run_one(self, tenant: UUID, job: UUID) -> bool:
        specs = load_workflows(self.cfg.config_dir)
        targets = load_targets(self.cfg.config_dir)
        vault = Vault(Envelope(self.cfg.vault.master_key_b64.get_secret_value(), self.cfg.vault.key_id))
        async with tenant_tx(self.engine, tenant) as conn:
            held = await jobs.take(conn, tenant, job, self.worker_id, self.cfg.workflows.lease_s)
            if held is None:
                return False
            row = (
                (
                    await conn.execute(
                        text("SELECT * FROM workflow_jobs WHERE tenant_id=:t AND id=:j"), {"t": tenant, "j": job}
                    )
                )
                .mappings()
                .one()
            )
            account_row = (
                (
                    await conn.execute(
                        text("SELECT * FROM accounts WHERE tenant_id=:t AND id=:a"),
                        {"t": tenant, "a": row["account_id"]},
                    )
                )
                .mappings()
                .one()
            )
            account = Account(
                tenant,
                account_row["id"],
                account_row["target"],
                account_row["username"],
                account_row["email"],
                account_row["account_group"],
                account_row["otp_channel"],
            )
            stored = await vault.load(conn, account)
            password = None if stored and stored.state == "fresh" else await vault.password(conn, account)
        spec = specs.get(row["workflow"])
        adapter = BrowserWorkflow(self.cfg, self.browser, self.otp)
        context = None
        acting = False
        try:
            context, page = await adapter.open(
                account,
                targets.authentication(account.target),
                password,
                stored.storage_state if stored and password is None else None,
            )
            await adapter.prepare(page, spec, row["inputs"])
            async with tenant_tx(self.engine, tenant) as conn:
                await vault.save(conn, account, dict(await context.storage_state()))
                acting = await jobs.begin_action(conn, held, spec, self.cfg.workflows)
                if not acting:
                    await jobs.reject_before_action(conn, held)
            if not acting:
                return False
            try:
                async with asyncio.timeout(self.cfg.workflows.action_timeout_ms / 1000):
                    status = await adapter.perform(page, spec, row["inputs"])
                    verified, receipt_hash = await adapter.receipt(context, spec, row["inputs"])
                outcome: Literal["CONFIRMED", "FAILED", "UNKNOWN"] = (
                    "CONFIRMED" if verified else "FAILED" if status in spec.failure_statuses else "UNKNOWN"
                )
                async with tenant_tx(self.engine, tenant) as conn:
                    recorded = await jobs.finish(
                        conn, held, outcome, {"status": status, "receipt_hash": receipt_hash, "verified": verified}
                    )
                    if not recorded:
                        log.warning(
                            "workflow result lost its lease; recovery must reconcile", extra={"job_id": str(job)}
                        )
            except Exception:
                async with tenant_tx(self.engine, tenant) as conn:
                    await jobs.finish(conn, held, "UNKNOWN", {"reason": "response_interrupted"})
            return True
        except Exception:
            # Pre-action failure is safe to retry after lease recovery; no action was authorized.
            log.warning("workflow attempt interrupted", extra={"job_id": str(job), "acting": acting})
            return False
        finally:
            if context is not None:
                await context.close()

    async def reconcile_one(self, tenant: UUID, row: dict[str, Any]) -> None:
        specs = load_workflows(self.cfg.config_dir)
        spec = specs.get(row["workflow"])
        if spec.fingerprint != row["contract_hash"]:
            return  # changed adapter cannot reinterpret old evidence
        vault = Vault(Envelope(self.cfg.vault.master_key_b64.get_secret_value(), self.cfg.vault.key_id))
        async with tenant_tx(self.engine, tenant) as conn:
            account_row = (
                (
                    await conn.execute(
                        text("SELECT * FROM accounts WHERE tenant_id=:t AND id=:a"),
                        {"t": tenant, "a": row["account_id"]},
                    )
                )
                .mappings()
                .one()
            )
            account = Account(
                tenant,
                account_row["id"],
                account_row["target"],
                account_row["username"],
                account_row["email"],
                account_row["account_group"],
                account_row["otp_channel"],
            )
            stored = await vault.load(conn, account)
        if stored is None:
            return
        adapter = BrowserWorkflow(self.cfg, self.browser, self.otp)
        context, _page = await adapter.open(
            account,
            load_targets(self.cfg.config_dir).authentication(account.target),
            None,
            stored.storage_state,
        )
        try:
            verified, receipt_hash = await adapter.receipt(context, spec, row["inputs"])
            async with tenant_tx(self.engine, tenant) as conn:
                await jobs.reconcile(
                    conn, tenant, row["id"], row["action_hash"], "CONFIRMED" if verified else None, receipt_hash
                )
        finally:
            await context.close()

    async def tick(self) -> None:
        async with system_tx(self.engine) as conn:
            tenants = list((await conn.execute(text("SELECT id FROM tenants"))).scalars())
        for tenant in tenants:
            async with tenant_tx(self.engine, tenant) as conn:
                await jobs.recover(conn, tenant, self.cfg.workflows.evidence_page_size)
                ready = await jobs.ready_jobs(conn, tenant, self.cfg.workflows.evidence_page_size)
                rows = await jobs.reconciliation_batch(conn, tenant, self.cfg.workflows)
            for job_id in ready:
                await self.run_one(tenant, job_id)
            for row in rows:
                try:
                    await self.reconcile_one(tenant, dict(row))
                except Exception:
                    log.warning("workflow reconciliation unavailable", extra={"job_id": str(row["id"])})


async def main() -> None:
    cfg = load(WorkflowAppSettings)
    engine = make_engine(cfg.app_db.dsn, cfg.app_db, "fw-workflows")
    otp = MailpitOtp(cfg.mailpit.api_url, cfg.board_client.timeout_s)
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=cfg.worker.headless)
            try:
                runner = Runner(cfg, engine, browser, otp, f"workflow-{uuid4().hex}")
                while True:
                    await runner.tick()
                    await asyncio.sleep(cfg.workflows.poll_s)
            finally:
                await browser.close()
    finally:
        await otp.aclose()
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
