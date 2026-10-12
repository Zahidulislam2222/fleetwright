"""Real approval UI against real authenticated API handlers (no fabricated response bodies)."""

import asyncio
import shutil
import socket
from pathlib import Path
from uuid import UUID

import httpx
import pytest
from playwright.async_api import Route, async_playwright
from test_workflows import proposal

from apikit import Api
from fw_core import workflows as jobs
from fw_core.db import tenant_tx

ROOT = Path(__file__).resolve().parents[3]
pytestmark = [pytest.mark.integration, pytest.mark.browser]


async def test_owner_reviews_exact_proposal_before_approval_in_browser(api: Api) -> None:
    _, job, _, _ = await proposal(api)
    node = shutil.which("node")
    assert node and (ROOT / "apps/dashboard/.next/BUILD_ID").is_file(), "Build the dashboard before its browser gate"
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
    client = await api.signed_in("owner")
    origin = f"http://127.0.0.1:{port}"
    try:
        async with asyncio.timeout(45), httpx.AsyncClient() as probe:
            while True:
                assert process.returncode is None, "dashboard server exited"
                try:
                    if (await probe.get(origin)).status_code == 200:
                        break
                except httpx.TransportError:
                    pass
                await asyncio.sleep(0.2)
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            try:
                page = await browser.new_page(viewport={"width": 1100, "height": 850})

                async def api_request(route: Route) -> None:
                    if route.request.url.endswith("/v1/stream"):
                        await route.abort()
                        return
                    path = route.request.url.removeprefix(origin)
                    response = await client.request(
                        route.request.method,
                        path,
                        content=route.request.post_data,
                        headers={
                            k: v
                            for k, v in route.request.headers.items()
                            if k.lower() in {"content-type", api.cfg.auth.csrf_header.lower()}
                        },
                    )
                    await route.fulfill(
                        status=response.status_code,
                        body=response.content,
                        content_type=response.headers.get("content-type", "application/json"),
                    )

                await page.route("**/v1/**", api_request)
                await page.goto(origin + "/console/workflows")
                await page.get_by_role("button", name="Refresh", exact=True).click()
                await (
                    page.get_by_role("listitem")
                    .filter(has_text=job["identity"])
                    .get_by_role("button", name="Review proposal")
                    .click()
                )
                approval = page.get_by_role("button", name="Approve this exact action")
                await approval.wait_for()
                assert await approval.is_disabled()
                assert await page.get_by_text(job["action_hash"], exact=True).is_visible()
                assert await page.get_by_text("Repair demonstration", exact=False).is_visible()
                await page.get_by_role("checkbox", name="I reviewed the account and every input below.").check()
                await approval.click()
                await page.get_by_text(
                    "Approval recorded. A worker will recheck authorization before acting."
                ).wait_for()
                async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
                    assert (await jobs.inspect(conn, api.tenant_id, UUID(job["id"])))["state"] == "QUEUED"
                    await jobs.cancel(conn, api.tenant_id, UUID(job["id"]))
                async with page.expect_download() as download:
                    await page.get_by_role("button", name="Download evidence page").click()
                artifacts = ROOT / "var/test-artifacts"
                artifacts.mkdir(parents=True, exist_ok=True)
                await (await download.value).save_as(artifacts / "workflow-console-evidence.json")
                await page.screenshot(path=str(artifacts / "workflow-console.png"), full_page=True)
            finally:
                await browser.close()
    finally:
        await client.aclose()
        process.terminate()
        await process.wait()
