"""Real Chromium acceptance: both owned workflows and post-acceptance crash reconciliation."""

from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from playwright.async_api import async_playwright
from sqlalchemy import text
from test_workflows import proposal

from apikit import Api
from boardkit import Board
from fw_browser.otp import MailpitOtp
from fw_browser.workflows import BrowserWorkflow
from fw_core import workflows as jobs
from fw_core.db import tenant_tx
from fw_core.settings import WorkflowAppSettings, load
from fw_core.workflow_contracts import load_workflows
from fw_worker.workflows import Runner

pytestmark = [pytest.mark.integration, pytest.mark.browser]
ROOT = Path(__file__).resolve().parents[3]


async def configure(api: Api, job: dict, reference: str | None = None) -> UUID:
    key = UUID(job["id"])
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        user = await conn.scalar(text("SELECT id FROM users WHERE tenant_id=:t AND role='owner'"), {"t": api.tenant_id})
        if reference is not None:
            row = (
                (
                    await conn.execute(
                        text("SELECT * FROM workflow_jobs WHERE tenant_id=:t AND id=:j"), {"t": api.tenant_id, "j": key}
                    )
                )
                .mappings()
                .one()
            )
            # Rewrite only before approval by creating a new action through the public core.
            await jobs.cancel(conn, api.tenant_id, key)
            grant = row["grant_id"]
            access = jobs.Access(api.tenant_id, grant, user, frozenset({"observe", "execute"}))
            spec = load_workflows(api.cfg.config_dir).get("freight-booking")
            updated = await jobs.submit(
                conn, access, uuid4().hex, "freight-booking", spec, row["account_id"], {"reference": reference}
            )
            key, job = UUID(updated["id"]), updated
        await jobs.approve(conn, api.tenant_id, key, job["action_hash"], user, 300)
    return key


@pytest.mark.parametrize("workflow", ["freight-booking", "service-request"])
async def test_real_browser_workflow_confirms_receipt(api: Api, board: Board, workflow: str) -> None:
    _access, job, _user, _token = await proposal(api, workflow)
    reference = None
    if workflow == "freight-booking":
        for _ in range(100):
            rows = board.admin.get("/api/public/recent").json()["loads"]
            opened = [row for row in rows if row["status"] == "open"]
            if opened:
                reference = opened[0]["ref"]
                break
            await asyncio.sleep(0.1)
        assert reference is not None
    key = await configure(api, job, reference)
    base = load(WorkflowAppSettings)
    cfg = base.model_copy(update={"app_db": api.cfg.app_db, "board_client": api.cfg.board_client})
    otp = MailpitOtp(cfg.mailpit.api_url)
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                runner = Runner(cfg, api.app.state.services.engine, browser, otp, "browser-test-" + uuid4().hex)
                assert await runner.run_one(api.tenant_id, key)
                async with tenant_tx(runner.engine, api.tenant_id) as conn:
                    assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "CONFIRMED"
            finally:
                await browser.close()
    finally:
        await otp.aclose()


async def test_process_killed_after_acceptance_reconciles_after_lease_expiry(api: Api, board: Board) -> None:
    _access, job, _user, _token = await proposal(api)
    key = await configure(api, job)
    artifact = ROOT / "var" / "test-artifacts" / (uuid4().hex + ".accepted")
    artifact.parent.mkdir(parents=True, exist_ok=True)
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        str(Path(__file__).with_name("workflow_crash_child.py")),
        str(api.tenant_id),
        str(key),
        str(artifact),
        env={
            **os.environ,
            "FW_BOARD_CLIENT__INTERNAL_URL": board.url,
            "FW_WORKFLOWS__LEASE_S": "10",
            "FW_WORKFLOWS__ACTION_TIMEOUT_MS": "2000",
        },
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        async with asyncio.timeout(45):
            while not artifact.exists():
                assert process.returncode is None, "worker exited before destination acceptance"
                await asyncio.sleep(0.1)
        process.kill()
        await process.wait()
        engine = api.app.state.services.engine
        async with asyncio.timeout(20):
            while True:
                async with tenant_tx(engine, api.tenant_id) as conn:
                    await jobs.recover(conn, api.tenant_id, 1000)
                    info = await jobs.inspect(conn, api.tenant_id, key)
                    if info["state"] == "UNKNOWN":
                        row = (
                            (
                                await conn.execute(
                                    text("SELECT * FROM workflow_jobs WHERE tenant_id=:t AND id=:j"),
                                    {"t": api.tenant_id, "j": key},
                                )
                            )
                            .mappings()
                            .one()
                        )
                        break
                await asyncio.sleep(0.1)
        base = load(WorkflowAppSettings)
        cfg = base.model_copy(update={"app_db": api.cfg.app_db, "board_client": api.cfg.board_client})
        otp = MailpitOtp(cfg.mailpit.api_url)
        try:
            async with async_playwright() as pw:
                browser = await pw.chromium.launch(headless=True)
                try:
                    runner = Runner(cfg, engine, browser, otp, "replacement-worker")
                    assert not await runner.run_one(api.tenant_id, key)
                    await runner.reconcile_one(api.tenant_id, dict(row))
                    async with tenant_tx(engine, api.tenant_id) as conn:
                        assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "CONFIRMED"
                        count = await conn.scalar(
                            text("""SELECT count(*) FROM workflow_events
                            WHERE tenant_id=:t AND job_id=:j AND kind='acting'"""),
                            {"t": api.tenant_id, "j": key},
                        )
                        assert count == 1
                finally:
                    await browser.close()
        finally:
            await otp.aclose()
    finally:
        if process.returncode is None:
            process.kill()
            await process.wait()


async def test_browser_lost_response_reconciles_without_second_click(
    api: Api, board: Board, monkeypatch: pytest.MonkeyPatch
) -> None:
    _access, job, _user, _token = await proposal(api)
    key = await configure(api, job)
    original = BrowserWorkflow.perform
    clicks = 0

    async def interrupted(self, page, spec, inputs):
        nonlocal clicks
        clicks += 1
        assert await original(self, page, spec, inputs) == 201
        raise ConnectionError("simulate worker response interruption after destination commit")

    monkeypatch.setattr(BrowserWorkflow, "perform", interrupted)
    base = load(WorkflowAppSettings)
    cfg = base.model_copy(update={"app_db": api.cfg.app_db, "board_client": api.cfg.board_client})
    otp = MailpitOtp(cfg.mailpit.api_url)
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                runner = Runner(cfg, api.app.state.services.engine, browser, otp, "crash-test-" + uuid4().hex)
                assert await runner.run_one(api.tenant_id, key)
                async with tenant_tx(runner.engine, api.tenant_id) as conn:
                    assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "UNKNOWN"
                    row = (
                        (
                            await conn.execute(
                                text("SELECT * FROM workflow_jobs WHERE tenant_id=:t AND id=:j"),
                                {"t": api.tenant_id, "j": key},
                            )
                        )
                        .mappings()
                        .one()
                    )
                assert not await runner.run_one(api.tenant_id, key)
                await runner.reconcile_one(api.tenant_id, dict(row))
                async with tenant_tx(runner.engine, api.tenant_id) as conn:
                    assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "CONFIRMED"
                assert clicks == 1
            finally:
                await browser.close()
    finally:
        await otp.aclose()
