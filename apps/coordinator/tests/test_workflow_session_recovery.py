"""Expired or revoked cached destination sessions must not strand approved workflows."""

import asyncio
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest
from playwright.async_api import async_playwright
from sqlalchemy import text
from test_workflow_browser import configure
from test_workflows import proposal

from apikit import Api
from boardkit import Board
from fw_browser.otp import MailpitOtp
from fw_browser.workflows import BrowserWorkflow
from fw_core import workflows as jobs
from fw_core.crypto import Envelope
from fw_core.db import tenant_tx
from fw_core.settings import WorkflowAppSettings, load
from fw_core.vault import Account, Vault
from fw_worker.workflows import Runner

pytestmark = [pytest.mark.integration, pytest.mark.browser]


async def invalidate(api: Api, board: Board, account_id: UUID, mode: str) -> None:
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        row = (
            (
                await conn.execute(
                    text("SELECT * FROM accounts WHERE tenant_id=:t AND id=:a"), {"t": api.tenant_id, "a": account_id}
                )
            )
            .mappings()
            .one()
        )
        account = Account(
            api.tenant_id,
            account_id,
            row["target"],
            row["username"],
            row["email"],
            row["account_group"],
            row["otp_channel"],
        )
        vault = Vault(Envelope(api.cfg.vault.master_key_b64.get_secret_value(), api.cfg.vault.key_id))
        stored = await vault.load(conn, account)
        assert stored is not None
        if mode == "expired":
            for cookie in stored.storage_state["cookies"]:
                cookie["expires"] = (datetime.now(UTC) - timedelta(seconds=60)).timestamp()
            await vault.save(conn, account, stored.storage_state)
        else:
            board.admin.post("/admin/sessions/expire", json={"username": account.username}).raise_for_status()


@pytest.mark.parametrize("mode", ["expired", "revoked"])
async def test_execution_refreshes_unusable_cached_session(api: Api, board: Board, mode: str) -> None:
    base = load(WorkflowAppSettings)
    cfg = base.model_copy(update={"app_db": api.cfg.app_db, "board_client": api.cfg.board_client})
    otp = MailpitOtp(cfg.mailpit.api_url)
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                runner = Runner(cfg, api.app.state.services.engine, browser, otp, "session-test-" + uuid4().hex)
                _access, first, _owner, _token = await proposal(api)
                assert await runner.run_one(api.tenant_id, await configure(api, first))
                await invalidate(api, board, UUID(first["account_id"]), mode)
                _access, second, _owner, _token = await proposal(api)
                key = await configure(api, second)
                assert await runner.run_one(api.tenant_id, key)
                async with tenant_tx(runner.engine, api.tenant_id) as conn:
                    assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "CONFIRMED"
                    assert (
                        await conn.scalar(
                            text(
                                "SELECT count(*) FROM workflow_events WHERE tenant_id=:t AND job_id=:j AND kind='acting'"
                            ),
                            {"t": api.tenant_id, "j": key},
                        )
                        == 1
                    )
            finally:
                await browser.close()
    finally:
        await otp.aclose()


@pytest.mark.parametrize("recovery_condition", ["available", "busy", "unavailable", "delayed", "stolen"])
async def test_reconciliation_refreshes_expired_session_without_another_action(
    api: Api, board: Board, monkeypatch: pytest.MonkeyPatch, recovery_condition: str
) -> None:
    _access, job, _owner, _token = await proposal(api)
    key = await configure(api, job)
    original = BrowserWorkflow.perform
    actions = 0

    async def interrupted(self, page, spec, inputs):
        nonlocal actions
        actions += 1
        assert await original(self, page, spec, inputs) == 201
        raise ConnectionError("test response interruption after accepted action")

    monkeypatch.setattr(BrowserWorkflow, "perform", interrupted)
    base = load(WorkflowAppSettings)
    cfg = base.model_copy(update={"app_db": api.cfg.app_db, "board_client": api.cfg.board_client})
    otp = MailpitOtp(cfg.mailpit.api_url)
    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                runner = Runner(cfg, api.app.state.services.engine, browser, otp, "receipt-test-" + uuid4().hex)
                assert await runner.run_one(api.tenant_id, key)
                await invalidate(api, board, UUID(job["account_id"]), "expired")
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
                if recovery_condition == "busy":
                    async with tenant_tx(runner.engine, api.tenant_id) as conn:
                        await conn.execute(
                            text(
                                """UPDATE accounts SET holder_worker='test-other-worker',
                                holder_expires_at=clock_timestamp()+interval '1 minute' WHERE tenant_id=:t AND id=:a"""
                            ),
                            {"t": api.tenant_id, "a": UUID(job["account_id"])},
                        )
                    await runner.reconcile_one(api.tenant_id, dict(row))
                    async with tenant_tx(runner.engine, api.tenant_id) as conn:
                        assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "UNKNOWN"
                        assert (
                            await conn.scalar(
                                text("SELECT holder_worker FROM accounts WHERE tenant_id=:t AND id=:a"),
                                {"t": api.tenant_id, "a": UUID(job["account_id"])},
                            )
                            == "test-other-worker"
                        )
                        await conn.execute(
                            text(
                                "UPDATE accounts SET holder_worker=NULL,holder_expires_at=NULL WHERE tenant_id=:t AND id=:a"
                            ),
                            {"t": api.tenant_id, "a": UUID(job["account_id"])},
                        )
                if recovery_condition == "unavailable":

                    async def unavailable(self, account, *args):
                        raise ConnectionError("test authentication outage")

                    with monkeypatch.context() as outage:
                        outage.setattr(Runner, "open_account", unavailable)
                        with pytest.raises(ConnectionError):
                            await runner.reconcile_one(api.tenant_id, dict(row))
                    async with tenant_tx(runner.engine, api.tenant_id) as conn:
                        assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "UNKNOWN"
                        assert (
                            await conn.scalar(
                                text("SELECT holder_worker FROM accounts WHERE tenant_id=:t AND id=:a"),
                                {"t": api.tenant_id, "a": UUID(job["account_id"])},
                            )
                            is None
                        )
                if recovery_condition == "delayed":
                    runner.cfg = cfg.model_copy(
                        update={
                            "workflows": cfg.workflows.model_copy(
                                update={"lease_s": 0.5, "lease_margin_s": 0.1, "action_timeout_ms": 100}
                            )
                        }
                    )

                    async def delayed(self, account, *args):
                        await asyncio.sleep(2)
                        raise ConnectionError("test authentication exceeded reservation")

                    with monkeypatch.context() as delay:
                        delay.setattr(Runner, "open_account", delayed)
                        with pytest.raises(TimeoutError):
                            await runner.reconcile_one(api.tenant_id, dict(row))
                    runner.cfg = cfg
                    async with tenant_tx(runner.engine, api.tenant_id) as conn:
                        assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "UNKNOWN"
                        assert (
                            await conn.scalar(
                                text("SELECT holder_worker FROM accounts WHERE tenant_id=:t AND id=:a"),
                                {"t": api.tenant_id, "a": UUID(job["account_id"])},
                            )
                            is None
                        )
                if recovery_condition == "stolen":
                    original_open = BrowserWorkflow.open

                    async def stolen(self, account, *args):
                        result = await original_open(self, account, *args)
                        async with tenant_tx(runner.engine, api.tenant_id) as conn:
                            await conn.execute(
                                text(
                                    "UPDATE accounts SET holder_worker='test-new-holder' WHERE tenant_id=:t AND id=:a"
                                ),
                                {"t": api.tenant_id, "a": account.id},
                            )
                        return result

                    with monkeypatch.context() as theft:
                        theft.setattr(BrowserWorkflow, "open", stolen)
                        with pytest.raises(jobs.Conflict):
                            await runner.reconcile_one(api.tenant_id, dict(row))
                    async with tenant_tx(runner.engine, api.tenant_id) as conn:
                        assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "UNKNOWN"
                        assert (
                            await conn.scalar(
                                text("SELECT holder_worker FROM accounts WHERE tenant_id=:t AND id=:a"),
                                {"t": api.tenant_id, "a": UUID(job["account_id"])},
                            )
                            == "test-new-holder"
                        )
                        await conn.execute(
                            text(
                                "UPDATE accounts SET holder_worker=NULL,holder_expires_at=NULL WHERE tenant_id=:t AND id=:a"
                            ),
                            {"t": api.tenant_id, "a": UUID(job["account_id"])},
                        )
                await runner.reconcile_one(api.tenant_id, dict(row))
                async with tenant_tx(runner.engine, api.tenant_id) as conn:
                    assert (await jobs.inspect(conn, api.tenant_id, key))["state"] == "CONFIRMED"
                assert actions == 1
            finally:
                await browser.close()
    finally:
        await otp.aclose()
