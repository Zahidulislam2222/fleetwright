"""Real untrusted-page WebSocket handshake regression, including isolated CDP attachment."""

from __future__ import annotations

import asyncio
import json
import socket
import uuid

import pytest
from fw_agent.browser import Browser
from playwright.async_api import async_playwright

from fw_core.settings import AgentAppSettings

from .conftest import ROOT


@pytest.mark.browser
@pytest.mark.parametrize("attach", [False, True], ids=["dedicated", "cdp"])
async def test_untrusted_source_cannot_open_off_origin_websocket(
    agent_settings: AgentAppSettings, attach: bool
) -> None:
    attempts: list[str] = []

    async def sink(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        try:
            header = await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
            attempts.append(header.decode())
            writer.write(b"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
            await writer.drain()
        finally:
            writer.close()
            await writer.wait_closed()

    ws_server = await asyncio.start_server(sink, "127.0.0.1", 0)
    ws_port = ws_server.sockets[0].getsockname()[1]
    html = (
        "<!doctype html><title>Untrusted owned source</title><article id='source'>Owned fixture</article>"
        "<script>window.wsDone=false;const socket=new WebSocket(" + json.dumps(f"ws://127.0.0.1:{ws_port}/exfil") + ");"
        "socket.onerror=()=>window.wsDone=true;socket.onclose=()=>window.wsDone=true;</script>"
    ).encode()

    async def source(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        await asyncio.wait_for(reader.readuntil(b"\r\n\r\n"), timeout=5)
        writer.write(
            (
                "HTTP/1.1 200 OK\r\nContent-Type: text/html\r\nConnection: close\r\n"
                f"Content-Length: {len(html)}\r\n\r\n"
            ).encode()
            + html
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    http_server = await asyncio.start_server(source, "127.0.0.1", 0)
    source_port = http_server.sockets[0].getsockname()[1]
    destination = f"http://127.0.0.1:{source_port}"
    async with ws_server, http_server, async_playwright() as playwright:
        # An independent unguarded browser proves the page executes the socket attempt and the
        # observing sink is reachable. A socket error by itself would be vacuous evidence.
        control_browser = await playwright.chromium.launch()
        try:
            control_page = await control_browser.new_page()
            await control_page.goto(destination)
            await control_page.wait_for_function("window.wsDone === true")
            assert len(attempts) == 1
            assert attempts[0].startswith("GET /exfil HTTP/1.1\r\n")
            assert "\r\nupgrade: websocket\r\n" in attempts[0].lower()
            positive_control_contacts = len(attempts)
        finally:
            await control_browser.close()
        attempts.clear()
        owner_browser = None
        owner_tab = None
        config = agent_settings.agent.model_copy(update={"allowed_origins": [destination]})
        if attach:
            with socket.socket() as listener:
                listener.bind(("127.0.0.1", 0))
                cdp_port = listener.getsockname()[1]
            owner_browser = await playwright.chromium.launch(args=[f"--remote-debugging-port={cdp_port}"])
            owner_tab = await owner_browser.new_page()
            await owner_tab.set_content("<title>Keep owner tab</title><p id='owner'>Unchanged owner content</p>")
            config = config.model_copy(update={"cdp_url": f"http://127.0.0.1:{cdp_port}"})
        browser = Browser(config)
        try:
            async with browser.tabs(destination) as pages:
                await pages[0].goto(destination)
                await pages[0].wait_for_function("window.wsDone === true")
            evidence = ROOT / "var" / "agent-proof" / "ws-egress"
            evidence.mkdir(parents=True, exist_ok=True)
            (evidence / f"{'cdp' if attach else 'dedicated'}-{uuid.uuid4().hex}.json").write_text(
                json.dumps(
                    {
                        "attach": attach,
                        "http_source_port": source_port,
                        "off_origin_socket_port": ws_port,
                        "positive_control_contacts": positive_control_contacts,
                        "sink_rejection_status": 403,
                        "guarded_upgrade_attempts": len(attempts),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )
            assert attempts == [], "untrusted source escaped the guard through a WebSocket connection attempt"
        finally:
            await browser.stop()
            if owner_browser is not None and owner_tab is not None:
                assert owner_browser.is_connected()
                assert not owner_tab.is_closed()
                assert await owner_tab.title() == "Keep owner tab"
                assert await owner_tab.locator("#owner").inner_text() == "Unchanged owner content"
                await owner_browser.close()
