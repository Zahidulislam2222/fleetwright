"""Pause after real acceptance so the parent can kill this worker before confirmation."""

import asyncio
import sys
from pathlib import Path
from uuid import UUID

from playwright.async_api import async_playwright

from fw_browser.otp import MailpitOtp
from fw_browser.workflows import BrowserWorkflow
from fw_core.db import make_engine
from fw_core.settings import WorkflowAppSettings, load
from fw_worker.workflows import Runner


async def main() -> None:
    tenant, job, marker = UUID(sys.argv[1]), UUID(sys.argv[2]), Path(sys.argv[3])
    cfg = load(WorkflowAppSettings)
    engine = make_engine(cfg.app_db.dsn, cfg.app_db, "crash-child")
    otp = MailpitOtp(cfg.mailpit.api_url)
    perform = BrowserWorkflow.perform

    async def pause_after_acceptance(self, page, spec, inputs):
        status = await perform(self, page, spec, inputs)
        if status != 201:
            raise RuntimeError("destination did not accept")
        marker.write_text("accepted", encoding="utf-8")
        await asyncio.Event().wait()

    BrowserWorkflow.perform = pause_after_acceptance
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=True)
        await Runner(cfg, engine, browser, otp, "killed-worker").run_one(tenant, job)


if __name__ == "__main__":
    asyncio.run(main())
