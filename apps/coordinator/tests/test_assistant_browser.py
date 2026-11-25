"""The help assistant panel in the real console build: a full-height, opaque drawer above the page
(not trapped inside the sticky header), and a question answered with a marked answer card."""

import asyncio
import shutil
import socket
from pathlib import Path

import httpx
import pytest
from playwright.async_api import Route, async_playwright, expect

from apikit import Api

ROOT = Path(__file__).resolve().parents[3]
pytestmark = [pytest.mark.integration, pytest.mark.browser]


def check(condition: object, message: str) -> None:
    if not condition:
        pytest.fail(message)


async def test_assistant_drawer_covers_the_viewport_and_answers(api: Api) -> None:
    node = shutil.which("node")
    check(node and (ROOT / "apps/dashboard/.next/BUILD_ID").is_file(), "build the dashboard first")
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    process = await asyncio.create_subprocess_exec(
        str(node),
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
    try:
        # Generous: a cold first render is slow on a busy machine; the check is layout, not speed.
        async with asyncio.timeout(120), httpx.AsyncClient(timeout=30) as probe:
            while True:
                check(process.returncode is None, "next start exited")
                try:
                    if (await probe.get(origin + "/console")).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.5)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1280, "height": 800})

                async def api_request(route: Route) -> None:
                    path = route.request.url.removeprefix(origin)
                    if path == "/v1/stream":
                        await route.abort()
                        return
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
                await page.goto(origin + "/console")
                await page.get_by_role("button", name="Open the help assistant").click()
                dialog = page.get_by_role("dialog")
                await expect(dialog).to_be_visible(timeout=30_000)
                box = await dialog.bounding_box()
                check(box is not None and box["height"] >= 800 - 1, f"drawer is not full height: {box}")
                background = await dialog.evaluate("e => getComputedStyle(e).backgroundColor")
                check(background not in ("rgba(0, 0, 0, 0)", "transparent"), f"drawer is transparent: {background}")
                inside_header = await dialog.evaluate("e => !!e.closest('header')")
                check(not inside_header, "drawer is rendered inside the sticky header")
                await page.get_by_label("Your question").fill("What happens to an UNKNOWN claim?")
                await page.get_by_label("Your question").press("Enter")
                answer = dialog.locator("article[data-ai-generated]")
                await expect(answer).to_be_visible(timeout=30_000)
                check(await answer.get_attribute("data-ai-generated") == "false", "AI is off in tests: search answer")
                # The drawer is the topmost element over the header area, not hidden behind it.
                on_top = await page.evaluate(
                    "() => !!document.elementFromPoint(innerWidth - 40, 20)?.closest('[role=dialog]')"
                )
                check(on_top, "drawer is not drawn above the header")
                await page.keyboard.press("Escape")
                await expect(dialog).to_be_hidden()
                await expect(page.get_by_role("button", name="Open the help assistant")).to_be_focused()

                # Phone width: the drawer covers the whole screen without horizontal scrolling.
                await page.set_viewport_size({"width": 375, "height": 812})
                await page.get_by_role("button", name="Open the help assistant").click()
                await expect(dialog).to_be_visible()
                phone = await dialog.bounding_box()
                check(phone is not None and phone["width"] >= 374 and phone["height"] >= 811, f"phone drawer: {phone}")
                overflow = await page.evaluate("() => document.documentElement.scrollWidth - innerWidth")
                check(overflow <= 0, f"horizontal overflow {overflow}px at 375px")
            finally:
                await browser.close()
    finally:
        await client.aclose()
        process.terminate()
        await process.wait()
