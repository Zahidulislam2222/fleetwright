"""Native review UI and isolated CDP attach must preserve the owner's browser."""

from __future__ import annotations

import asyncio
import socket
import uuid
from typing import Any

import httpx
import pytest
from fw_agent.browser import Browser
from fw_agent.contracts import Draft
from playwright.async_api import async_playwright

from fw_core.settings import AgentAppSettings

from .conftest import ROOT


@pytest.mark.browser
async def test_native_ui_review_edit_and_approve(
    agent_server: tuple[Any, httpx.AsyncClient], agent_settings: AgentAppSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, _ = agent_server

    async def draft(*_: Any) -> Draft:
        return Draft(title="Maintenance review", body="Review the refrigeration temperature warning before service.")

    monkeypatch.setattr(app.state.runner.model, "draft", draft)
    output = ROOT / "var" / "agent-proof" / f"ui-{uuid.uuid4().hex}"
    output.mkdir(parents=True)
    async with async_playwright() as playwright:
        browser = await playwright.chromium.launch()
        page = await browser.new_page(viewport={"width": 1280, "height": 1000})
        errors: list[str] = []
        page.on("pageerror", lambda error: errors.append(str(error)))
        await page.goto(agent_settings.agent.allowed_origins[0])
        await page.get_by_label("What should the draft say?").fill("Draft a maintenance note for review.")
        await page.get_by_role("button", name="Read pages and draft locally").click()
        await page.get_by_role("heading", name="Maintenance request · AWAITING_APPROVAL").wait_for()
        card = page.locator("article.task").first
        original_id = await card.locator("small").inner_text()
        edited_title = "Human-reviewed maintenance"
        edited_body = "Inspect tomorrow; preserve this exact reviewed instruction through refresh."
        await card.get_by_label("Draft title").fill(edited_title)
        await card.get_by_label("Draft body").fill(edited_body)
        await card.get_by_role("button", name="Approve this exact save").click()
        await page.get_by_role("alert").filter(has_text="Save your edits").wait_for()
        assert app.state.store.db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 0
        await page.get_by_role("button", name="Refresh", exact=True).click()
        await asyncio.sleep(app.state.runner.data.poll_interval_ms / 1000 * 2)
        assert await card.get_by_label("Draft title").input_value() == edited_title
        assert await card.get_by_label("Draft body").input_value() == edited_body
        await card.get_by_role("button", name="Save edits for fresh approval").click()
        async with asyncio.timeout(10):
            while await card.locator("small").inner_text() == original_id:
                await asyncio.sleep(0.05)
        replacement_id = await card.locator("small").inner_text()
        assert app.state.store.get(original_id)["state"] == "CANCELLED"
        assert app.state.store.get(replacement_id)["proposal"]["draft"] == {
            "title": edited_title,
            "body": edited_body,
        }
        await page.locator("article.task").first.get_by_role("button", name="Approve this exact save").click()
        await page.get_by_role("heading", name="Maintenance request · CONFIRMED").wait_for()
        assert app.state.store.db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 1
        receipt = app.state.store.receipt(replacement_id)
        assert receipt is not None
        assert receipt["title"] == edited_title and receipt["body"] == edited_body
        await page.screenshot(path=output / "desktop.png", full_page=True)
        await page.set_viewport_size({"width": 390, "height": 844})
        await page.screenshot(path=output / "mobile.png", full_page=True)
        assert await page.evaluate("document.documentElement.scrollWidth <= innerWidth")
        assert errors == []
        await browser.close()
    print(f"Agent native UI screenshots: {output}")


@pytest.mark.browser
async def test_cdp_attach_preserves_existing_tab(
    agent_server: tuple[Any, httpx.AsyncClient], agent_settings: AgentAppSettings
) -> None:
    app, _ = agent_server
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    async with async_playwright() as playwright:
        owner_browser = await playwright.chromium.launch(args=[f"--remote-debugging-port={port}"])
        owner_context = await owner_browser.new_context()
        owner_tab = await owner_context.new_page()
        await owner_tab.set_content("<title>Owner preserved</title><p id='original'>Keep this tab intact.</p>")
        original_url = owner_tab.url
        agent_browser = Browser(agent_settings.agent.model_copy(update={"cdp_url": f"http://127.0.0.1:{port}"}))
        source = await agent_browser.source(app.state.runner.data.templates[0], agent_settings.agent.allowed_origins[0])
        assert "DEMO-14" in source
        await agent_browser.stop()
        assert owner_browser.is_connected()
        assert not owner_tab.is_closed()
        assert owner_tab.url == original_url
        assert await owner_tab.title() == "Owner preserved"
        assert await owner_tab.locator("#original").inner_text() == "Keep this tab intact."
        await owner_browser.close()
