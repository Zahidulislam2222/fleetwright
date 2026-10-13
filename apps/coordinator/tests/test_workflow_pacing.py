"""Slow browser preparation/action cannot consume the next action's completion interval."""

import asyncio
from uuid import UUID, uuid4

import pytest
from playwright.async_api import async_playwright
from sqlalchemy import text
from test_workflow_browser import configure
from test_workflows import proposal

from apikit import Api
from fw_browser.otp import MailpitOtp
from fw_browser.workflows import BrowserWorkflow
from fw_core.db import tenant_tx
from fw_core.settings import WorkflowAppSettings, load
from fw_worker.workflows import Runner

pytestmark = [pytest.mark.integration, pytest.mark.browser]


async def test_workflow_completion_refreshes_budget_after_slow_prepare_and_action(
    api: Api, monkeypatch: pytest.MonkeyPatch
) -> None:
    _access, job, _owner, _token = await proposal(api)
    key = await configure(api, job)
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        await conn.execute(
            text("UPDATE accounts SET rate_limit_per_min=600 WHERE id=:a"), {"a": UUID(job["account_id"])}
        )
    original_prepare, original_perform = BrowserWorkflow.prepare, BrowserWorkflow.perform

    async def slow_prepare(self, page, spec, inputs):
        await asyncio.sleep(0.15)
        return await original_prepare(self, page, spec, inputs)

    async def slow_perform(self, page, spec, inputs):
        await asyncio.sleep(0.15)
        return await original_perform(self, page, spec, inputs)

    monkeypatch.setattr(BrowserWorkflow, "prepare", slow_prepare)
    monkeypatch.setattr(BrowserWorkflow, "perform", slow_perform)
    cfg = load(WorkflowAppSettings)
    cfg = cfg.model_copy(update={"app_db": api.cfg.app_db, "board_client": api.cfg.board_client})
    otp = MailpitOtp(cfg.mailpit.api_url)
    try:
        async with async_playwright() as playwright:
            browser = await playwright.chromium.launch(headless=True)
            try:
                runner = Runner(cfg, api.app.state.services.engine, browser, otp, "paced-" + uuid4().hex)
                assert await runner.run_one(api.tenant_id, key)
                async with tenant_tx(runner.engine, api.tenant_id) as conn:
                    assert await conn.scalar(
                        text("""SELECT a.next_action_at>=j.updated_at+
                        make_interval(secs=>60.0/a.rate_limit_per_min) FROM workflow_jobs j JOIN accounts a
                        ON a.tenant_id=j.tenant_id AND a.id=j.account_id WHERE j.tenant_id=:t AND j.id=:j
                        AND j.state='CONFIRMED'"""),
                        {"t": api.tenant_id, "j": key},
                    )
            finally:
                await browser.close()
    finally:
        await otp.aclose()
