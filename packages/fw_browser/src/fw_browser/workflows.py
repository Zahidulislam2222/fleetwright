"""Owned-origin browser adapter for general contracts. No agent-supplied selectors or URLs."""

from __future__ import annotations

import json
from typing import Any
from urllib.parse import urlsplit

from playwright.async_api import Browser, BrowserContext, Page, Route, WebSocketRoute

from fw_browser.login import SignInTimeouts, sign_in
from fw_browser.otp import OtpProvider
from fw_core.settings import WorkflowAppSettings
from fw_core.targets import AuthenticationSpec
from fw_core.vault import Account
from fw_core.workflow_contracts import WorkflowSpec, digest


class DestinationSessionExpired(Exception):
    """The owned destination rejected a cached authentication state before any action."""


class BrowserWorkflow:
    def __init__(self, cfg: WorkflowAppSettings, browser: Browser, otp: OtpProvider) -> None:
        self.cfg, self.browser, self.otp = cfg, browser, otp

    async def open(
        self, account: Account, target: AuthenticationSpec, password: str | None, storage_state: Any = None
    ) -> tuple[BrowserContext, Page]:
        origin = self.cfg.board_client.internal_url.rstrip("/")
        context = await self.browser.new_context(storage_state=storage_state, service_workers="block")
        page = await context.new_page()
        page.set_default_timeout(self.cfg.workflows.action_timeout_ms)

        async def guard(route: Route) -> None:
            requested, allowed = urlsplit(route.request.url), urlsplit(origin)
            if (requested.scheme, requested.netloc) != (allowed.scheme, allowed.netloc):
                await route.abort()
            else:
                await route.continue_()

        await context.route("**/*", guard)

        async def reject_socket(socket: WebSocketRoute) -> None:
            await socket.close()

        await context.route_web_socket("**/*", reject_socket)
        try:
            if password is not None:
                await sign_in(
                    page,
                    origin,
                    target,
                    username=account.username,
                    password=password,
                    otp_address=account.email,
                    otp=self.otp,
                    timeouts=SignInTimeouts(
                        self.cfg.worker.login_timeout_ms, self.cfg.worker.otp_wait_s, self.cfg.worker.otp_clock_margin_s
                    ),
                )
            response = await context.request.get(
                origin + target.api.me, max_redirects=0, timeout=self.cfg.workflows.action_timeout_ms
            )
            if response.status == 401 or (response.ok and (await response.json()).get("username") != account.username):
                raise DestinationSessionExpired("permitted destination account is not signed in")
            if not response.ok:
                raise ValueError("destination session check unavailable")
            return context, page
        except BaseException:
            await context.close()
            raise

    async def prepare(self, page: Page, spec: WorkflowSpec, inputs: dict[str, str]) -> None:
        spec.validate_inputs(inputs)
        await page.goto(self.cfg.board_client.internal_url.rstrip("/") + spec.page)
        for key, selector in spec.input_selectors.items():
            field = page.locator(selector)
            if await field.evaluate("element => element.tagName") == "SELECT":
                await field.select_option(inputs[key])
            else:
                await field.fill(inputs[key])
        await page.locator(spec.action_selector.format_map(inputs)).wait_for(state="visible")

    async def perform(self, page: Page, spec: WorkflowSpec, inputs: dict[str, str]) -> int:
        path = spec.action_path.format_map(inputs)
        async with page.expect_response(
            lambda response: urlsplit(response.url).path == path and response.request.method == "POST"
        ) as pending:
            await page.locator(spec.action_selector.format_map(inputs)).click()
        return (await pending.value).status

    async def receipt(self, context: BrowserContext, spec: WorkflowSpec, inputs: dict[str, str]) -> tuple[bool, str]:
        response = await context.request.get(
            self.cfg.board_client.internal_url.rstrip("/") + spec.receipt_path,
            params={"reference": inputs["reference"]},
            max_redirects=0,
            timeout=self.cfg.workflows.action_timeout_ms,
        )
        if not response.ok:
            return False, ""
        body = await response.body()
        if len(body) > self.cfg.workflows.response_max_bytes:
            return False, ""
        payload = json.loads(body)
        matches = [
            row for row in payload.get(spec.receipt_collection, []) if row.get(spec.receipt_key) == inputs["reference"]
        ]
        for row in matches:
            # The second workflow proves full payload identity, not only a matching reference.
            if all(row.get(key) == value for key, value in inputs.items() if key != "reference"):
                return True, digest(row)
        return False, ""
