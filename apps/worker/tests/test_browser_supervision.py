"""A lost browser/driver must reach the process supervisor, never remain a healthy retry loop."""

from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import psutil
import pytest

from fw_worker import __main__ as entry


@pytest.mark.parametrize("phase", ["send", "detach"])
@pytest.mark.parametrize("signal_during_probe", [False, True])
async def test_stalled_protocol_reaches_drain_with_or_without_sigterm(
    phase: str, signal_during_probe: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    entered = asyncio.Event()
    signals = {}
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "add_signal_handler", lambda sig, handler: signals.update({sig: handler}))

    class Session:
        async def send(self, _method):
            if phase == "send":
                entered.set()
                await asyncio.Event().wait()

        async def detach(self):
            entered.set()
            await asyncio.Event().wait()

    browser = SimpleNamespace(
        on=Mock(),
        remove_listener=Mock(),
        is_connected=lambda: False,
        new_browser_cdp_session=AsyncMock(return_value=Session()),
    )

    @asynccontextmanager
    async def playwright():
        yield SimpleNamespace(chromium=SimpleNamespace(launch=AsyncMock(return_value=browser)))

    monkeypatch.setattr(entry, "async_playwright", playwright)
    monkeypatch.setattr(entry, "setup_logging", Mock())
    monkeypatch.setattr(
        entry,
        "load",
        lambda _: SimpleNamespace(
            worker=SimpleNamespace(headless=True, heartbeat_s=0.01, action_timeout_ms=50), log_level="INFO"
        ),
    )
    fleet = SimpleNamespace(
        start=AsyncMock(),
        drain=AsyncMock(),
        engine=SimpleNamespace(dispose=AsyncMock()),
        events=SimpleNamespace(aclose=AsyncMock()),
        stream=SimpleNamespace(aclose=AsyncMock()),
        email_otp=SimpleNamespace(aclose=AsyncMock()),
        evidence=SimpleNamespace(prune=Mock()),
    )
    monkeypatch.setattr(entry, "build_fleet", lambda *_: fleet)
    task = asyncio.create_task(entry.main())
    try:
        await asyncio.wait_for(entered.wait(), 1)
        if signal_during_probe:
            signals[signal.SIGTERM]()
        with pytest.raises(RuntimeError, match="browser"):
            await asyncio.wait_for(asyncio.shield(task), 0.5)
        fleet.drain.assert_awaited_once()
        fleet.engine.dispose.assert_awaited_once()
        fleet.events.aclose.assert_awaited_once()
        fleet.stream.aclose.assert_awaited_once()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.browser
@pytest.mark.parametrize("failure", ["browser", "driver"])
async def test_real_browser_or_driver_loss_exits_after_cleanup(failure: str, monkeypatch: pytest.MonkeyPatch) -> None:
    started = asyncio.Event()
    captured = {}
    signals = {}
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "add_signal_handler", lambda sig, handler: signals.update({sig: handler}))
    monkeypatch.setattr(entry, "setup_logging", Mock())
    monkeypatch.setattr(
        entry,
        "load",
        lambda _: SimpleNamespace(
            worker=SimpleNamespace(headless=True, heartbeat_s=0.05, action_timeout_ms=5000), log_level="INFO"
        ),
    )
    fleet = SimpleNamespace(
        start=AsyncMock(side_effect=started.set),
        drain=AsyncMock(),
        engine=SimpleNamespace(dispose=AsyncMock()),
        events=SimpleNamespace(aclose=AsyncMock()),
        stream=SimpleNamespace(aclose=AsyncMock()),
        email_otp=SimpleNamespace(aclose=AsyncMock()),
        evidence=SimpleNamespace(prune=Mock()),
    )

    def build(_cfg, browser, _behaviours):
        captured["browser"] = browser
        return fleet

    monkeypatch.setattr(entry, "build_fleet", build)
    before = {p.pid for p in psutil.Process().children()}
    task = asyncio.create_task(entry.main())
    try:
        await asyncio.wait_for(started.wait(), 15)
        if failure == "browser":
            await captured["browser"].close()
        else:
            drivers = [p for p in psutil.Process().children() if p.pid not in before and "run-driver" in p.cmdline()]
            assert len(drivers) == 1, "only the driver created by this test may be terminated"
            drivers[0].kill()
            await asyncio.to_thread(drivers[0].wait, timeout=5)
        with pytest.raises(RuntimeError, match="browser"):
            await asyncio.wait_for(asyncio.shield(task), 5)
        fleet.drain.assert_awaited_once()
        fleet.engine.dispose.assert_awaited_once()
        fleet.events.aclose.assert_awaited_once()
        fleet.stream.aclose.assert_awaited_once()
        fleet.email_otp.aclose.assert_awaited_once()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)


@pytest.mark.browser
@pytest.mark.parametrize("drain_fails", [False, True])
async def test_signal_cleanup_closes_resources_and_retains_failure(
    drain_fails: bool, monkeypatch: pytest.MonkeyPatch
) -> None:
    started = asyncio.Event()
    signals = {}
    loop = asyncio.get_running_loop()
    monkeypatch.setattr(loop, "add_signal_handler", lambda sig, handler: signals.update({sig: handler}))
    monkeypatch.setattr(entry, "setup_logging", Mock())
    monkeypatch.setattr(
        entry,
        "load",
        lambda _: SimpleNamespace(
            worker=SimpleNamespace(headless=True, heartbeat_s=0.05, action_timeout_ms=5000), log_level="INFO"
        ),
    )
    failure = RuntimeError("test drain failure")
    fleet = SimpleNamespace(
        start=AsyncMock(side_effect=started.set),
        drain=AsyncMock(side_effect=failure if drain_fails else None),
        engine=SimpleNamespace(dispose=AsyncMock()),
        events=SimpleNamespace(aclose=AsyncMock()),
        stream=SimpleNamespace(aclose=AsyncMock()),
        email_otp=SimpleNamespace(aclose=AsyncMock()),
        evidence=SimpleNamespace(prune=Mock()),
    )
    monkeypatch.setattr(entry, "build_fleet", lambda *_: fleet)
    task = asyncio.create_task(entry.main())
    try:
        await asyncio.wait_for(started.wait(), 15)
        signals[signal.SIGTERM]()
        if drain_fails:
            with pytest.raises(RuntimeError, match="test drain failure"):
                await asyncio.wait_for(task, 5)
        else:
            await asyncio.wait_for(task, 5)
        fleet.engine.dispose.assert_awaited_once()
        fleet.events.aclose.assert_awaited_once()
        fleet.stream.aclose.assert_awaited_once()
        fleet.email_otp.aclose.assert_awaited_once()
    finally:
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
