"""Bounded browser adapter. Model output never reaches URL/selector/operation arguments."""

from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from urllib.parse import urlencode

from playwright.async_api import BrowserContext, Page, Playwright, Route, WebSocketRoute, async_playwright

from fw_agent.contracts import TEMPLATE_ACTION_COST, Draft, Template, loopback_url, origin
from fw_agent.privacy import private_directory, private_file
from fw_core.settings import AgentSettings


class Browser:
    def __init__(self, settings: AgentSettings) -> None:
        self.settings = settings
        self.allowed = {origin(value) for value in settings.allowed_origins}
        if any(origin(value) != value.rstrip("/") for value in settings.allowed_origins):
            raise ValueError("allowlist entries must be exact origins without paths")
        if settings.max_tabs < 2:
            raise ValueError("the source/form workflow requires a two-tab budget")
        self.lock = asyncio.Lock()
        self.playwright: Playwright | None = None
        self.context: BrowserContext | None = None
        self.pages: set[Page] = set()

    def destination(self, destination: str) -> str:
        if destination not in self.allowed:
            raise ValueError("destination is not an explicitly allowed origin")
        return destination

    async def _context(self) -> BrowserContext:
        if self.context is None:
            self.playwright = await async_playwright().start()
            if self.settings.cdp_url:
                loopback_url(self.settings.cdp_url)
                browser = await self.playwright.chromium.connect_over_cdp(self.settings.cdp_url)
                # An isolated context deliberately does not inherit the owner's tabs or login.
                self.context = await browser.new_context(service_workers="block")
            else:
                private_directory(self.settings.profile_directory)
                self.context = await self.playwright.chromium.launch_persistent_context(
                    str(self.settings.profile_directory), headless=self.settings.headless, service_workers="block"
                )
                # The dedicated profile belongs exclusively to this application.
                for existing in self.context.pages:
                    await existing.close()
            # HTTP routing does not intercept WebSockets. Register this lifetime policy before
            # any task page/navigation; never connect a routed socket to its remote server.
            await self.context.route_web_socket("**/*", self._block_web_socket)
            self.context.set_default_timeout(self.settings.action_timeout_ms)
        return self.context

    @staticmethod
    async def _block_web_socket(socket: WebSocketRoute) -> None:
        await socket.close(code=1008, reason="WebSocket transport is disabled for local agent workflows")

    @asynccontextmanager
    async def tabs(self, destination: str, post: tuple[str, dict[str, str]] | None = None) -> AsyncIterator[list[Page]]:
        self.destination(destination)
        async with self.lock:
            context = await self._context()
            owned: list[Page] = []
            posted = False
            requests = 0

            async def guard(route: Route) -> None:
                nonlocal posted, requests
                requests += 1
                try:
                    permitted = (
                        requests <= self.settings.max_requests
                        and origin(route.request.url) == destination
                        and route.request.frame.page in owned
                    )
                except ValueError:
                    permitted = False
                if permitted and route.request.method not in {"GET", "HEAD"}:
                    permitted = False
                    if (
                        post
                        and not posted
                        and route.request.method == "POST"
                        and route.request.url == destination + post[0]
                    ):
                        try:
                            permitted = route.request.post_data_json == post[1]
                        except (ValueError, json.JSONDecodeError):
                            permitted = False
                        if permitted:
                            posted = True
                if permitted:
                    await route.continue_()
                else:
                    await route.abort("blockedbyclient")

            await context.route("**/*", guard)
            try:
                for _ in range(2):
                    if len(self.pages) >= self.settings.max_tabs:
                        raise ValueError("browser tab budget exceeded")
                    page = await context.new_page()
                    self.pages.add(page)
                    owned.append(page)
                    # Popups cannot bypass the route on a newly-created task page.
                    page.on("popup", lambda popup: asyncio.create_task(popup.close()))
                yield owned
            finally:
                for page in owned:
                    self.pages.discard(page)
                    if not page.is_closed():
                        await page.close()
                await context.unroute("**/*", guard)

    async def source(self, template: Template, destination: str) -> str:
        async with self.tabs(destination) as pages:
            source_page, form_page = pages
            await source_page.goto(destination + template.source_path, wait_until="domcontentloaded")
            if origin(source_page.url) != destination:
                raise ValueError("source navigation changed origin")
            # Both real tabs are used: source content and destination structure are checked.
            await form_page.goto(destination + template.form_path, wait_until="domcontentloaded")
            await form_page.locator(template.title_selector).wait_for(state="attached")
            await form_page.locator(template.body_selector).wait_for(state="attached")
            return (await source_page.locator(template.source_selector).inner_text())[: self.settings.max_content_chars]

    async def execute(self, task_id: str, proposal_hash: str, proposal: dict[str, Any], token: str) -> dict[str, Any]:
        template = Template.model_validate(proposal["template"])
        draft = Draft.model_validate(proposal["draft"])
        destination = self.destination(proposal["origin"])
        if self.settings.max_actions < TEMPLATE_ACTION_COST:
            raise ValueError("template exceeds the configured browser action budget")
        payload = {"task_id": task_id, "hash": proposal_hash, "token": token, "title": draft.title, "body": draft.body}
        async with self.tabs(destination, (template.accept_path, payload)) as pages:
            source_page, form_page = pages
            await source_page.goto(destination + template.source_path, wait_until="domcontentloaded")
            query = urlencode({"task_id": task_id, "token": token})
            await form_page.goto(destination + template.form_path + "?" + query, wait_until="domcontentloaded")
            if origin(form_page.url) != destination:
                raise ValueError("destination navigation changed origin")
            await form_page.locator(template.task_selector).fill(task_id)
            await form_page.locator(template.hash_selector).fill(proposal_hash)
            await form_page.locator(template.title_selector).fill(draft.title)
            await form_page.locator(template.body_selector).fill(draft.body)
            await form_page.locator(template.submit_selector).click()
            await form_page.wait_for_function(
                "selector => Boolean(document.querySelector(selector)?.textContent)", arg=template.receipt_selector
            )
            receipt = json.loads(await form_page.locator(template.receipt_selector).inner_text())
            if not isinstance(receipt, dict):
                raise ValueError("destination receipt is invalid")
            await self._evidence(form_page, task_id)
            return receipt

    async def reconcile(self, task_id: str, proposal: dict[str, Any], token: str) -> dict[str, Any]:
        template = Template.model_validate(proposal["template"])
        destination = self.destination(proposal["origin"])
        async with self.tabs(destination) as pages:
            receipt_page = pages[0]
            query = urlencode({"task_id": task_id, "token": token})
            response = await receipt_page.goto(
                destination + template.receipt_path + "?" + query, wait_until="domcontentloaded"
            )
            if response is None or response.status != 200:
                raise ValueError("no destination receipt yet; outcome remains UNKNOWN")
            result = json.loads(await receipt_page.locator("body").inner_text())
            if not isinstance(result, dict):
                raise ValueError("destination receipt is invalid")
            return result

    async def _evidence(self, page: Page, task_id: str) -> None:
        path: Path = self.settings.evidence_directory
        evidence = path / f"{task_id}.png"
        await asyncio.to_thread(private_file, evidence)
        await page.screenshot(path=evidence, full_page=True)

    async def stop(self) -> None:
        for page in list(self.pages):
            if not page.is_closed():
                await page.close()
        self.pages.clear()
        if self.context:
            await self.context.close()
            self.context = None
        if self.playwright:
            await self.playwright.stop()
            self.playwright = None
