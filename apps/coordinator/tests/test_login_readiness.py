"""Real API handshake latency must not turn a live password form into an offline flow."""

import asyncio
import shutil
import socket
from pathlib import Path

import httpx
import pytest
from playwright.async_api import Route, async_playwright, expect

from apikit import PASSWORD, Api

ROOT = Path(__file__).resolve().parents[3]
pytestmark = [pytest.mark.integration, pytest.mark.browser]


async def test_login_waits_for_initial_session_before_accepting_password(api: Api) -> None:
    node = shutil.which("node")
    assert node and (ROOT / "apps/dashboard/.next/BUILD_ID").is_file()
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = await asyncio.create_subprocess_exec(
        node,
        "node_modules/next/dist/bin/next",
        "start",
        "--hostname",
        "127.0.0.1",
        "--port",
        str(port),
        cwd=ROOT / "apps/dashboard",
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    origin = f"http://127.0.0.1:{port}"
    client = api.client()
    pending = asyncio.Event()
    release = asyncio.Event()
    password_requests = []
    try:
        async with asyncio.timeout(45), httpx.AsyncClient() as probe:
            while True:
                assert process.returncode is None
                try:
                    if (await probe.get(origin)).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.2)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page()

                async def api_request(route: Route) -> None:
                    path = route.request.url.removeprefix(origin)
                    if path == "/v1/stream":
                        await route.abort()
                        return
                    if path == "/v1/session":
                        pending.set()
                        await release.wait()
                    if path == "/v1/auth/login":
                        password_requests.append(route.request.post_data)
                    response = await client.request(
                        route.request.method,
                        path,
                        content=route.request.post_data,
                        headers={"Content-Type": "application/json"},
                    )
                    await route.fulfill(
                        status=response.status_code, body=response.content, content_type="application/json"
                    )

                await page.route("**/v1/**", api_request)
                await page.goto(origin + "/login")
                await asyncio.wait_for(pending.wait(), 10)
                await page.locator("#email").fill(api.users["owner"].email)
                await page.locator("#password").fill(PASSWORD)
                button = page.locator("form button[type=submit]")
                assert await button.is_disabled(), "pending API handshake must prevent an offline password transition"
                await page.locator("#password").press("Enter")
                assert not await page.locator("#code").count()
                assert not password_requests
                release.set()
                await expect(button).to_be_enabled()
                await button.click()
                await page.locator("#code").wait_for()
                assert len(password_requests) == 1
            finally:
                release.set()
                await browser.close()
    finally:
        release.set()
        await client.aclose()
        process.terminate()
        await process.wait()
