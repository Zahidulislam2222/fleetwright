"""Signal shutdown must finish owned cleanup without hiding unrelated cancellation/failure."""

from __future__ import annotations

import asyncio
import signal
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from fw_coordinator import crawls


@pytest.mark.parametrize("stop_signal", [signal.SIGTERM, signal.SIGINT])
@pytest.mark.parametrize("native_fallback", [False, True])
async def test_signals_cancel_run_once_and_keep_guard_through_disposal(
    monkeypatch: pytest.MonkeyPatch, stop_signal: signal.Signals, native_fallback: bool
) -> None:
    loop = asyncio.get_running_loop()
    handlers = {}
    events = []
    original = object()

    def add(sig, callback):
        if native_fallback:
            raise NotImplementedError
        handlers[sig] = callback

    def native(sig, callback):
        if callback is original:
            events.append("restored")
        else:
            handlers[sig] = lambda: callback(sig, None)

    async def run(_self):
        assert signal.SIGTERM in handlers and signal.SIGINT in handlers
        loop.call_soon(handlers[stop_signal])
        try:
            await asyncio.Event().wait()
        finally:
            events.append("run-cleanup")
            handlers[stop_signal]()  # A repeated stop cannot interrupt child/process cleanup.
            await asyncio.sleep(0)
            events.append("run-cleaned")

    async def dispose():
        assert events[-1] == "run-cleaned"
        handlers[stop_signal]()  # Guard must remain installed through engine disposal too.
        await asyncio.sleep(0)
        events.append("disposed")

    engine = SimpleNamespace(dispose=AsyncMock(side_effect=dispose))
    monkeypatch.setattr(crawls, "signal", signal, raising=False)
    monkeypatch.setattr(loop, "add_signal_handler", add)
    monkeypatch.setattr(loop, "remove_signal_handler", lambda _sig: events.append("removed"))
    monkeypatch.setattr(crawls.signal, "getsignal", lambda _sig: original)
    monkeypatch.setattr(crawls.signal, "signal", native)
    monkeypatch.setattr(
        crawls, "load", lambda _model: SimpleNamespace(config_dir=None, app_db=SimpleNamespace(dsn=None))
    )
    monkeypatch.setattr(crawls, "definitions", lambda _directory: None)
    monkeypatch.setattr(crawls, "make_engine", lambda *_args: engine)
    monkeypatch.setattr(crawls.Crawler, "run", run)
    await crawls.main()
    engine.dispose.assert_awaited_once()
    assert events.count("run-cleanup") == 1 and events.index("disposed") < events.index("restored")


@pytest.mark.parametrize("failure", [RuntimeError("test-crawler-failed"), asyncio.CancelledError()])
async def test_unrelated_run_failure_propagates_after_engine_disposal(monkeypatch, failure):
    loop = asyncio.get_running_loop()
    engine = SimpleNamespace(dispose=AsyncMock())
    monkeypatch.setattr(crawls, "signal", signal, raising=False)
    monkeypatch.setattr(loop, "add_signal_handler", lambda *_args: None)
    monkeypatch.setattr(loop, "remove_signal_handler", lambda *_args: None)
    monkeypatch.setattr(crawls.signal, "signal", lambda *_args: None)
    monkeypatch.setattr(
        crawls, "load", lambda _model: SimpleNamespace(config_dir=None, app_db=SimpleNamespace(dsn=None))
    )
    monkeypatch.setattr(crawls, "definitions", lambda _directory: None)
    monkeypatch.setattr(crawls, "make_engine", lambda *_args: engine)
    monkeypatch.setattr(crawls.Crawler, "run", AsyncMock(side_effect=failure))
    with pytest.raises(type(failure)) as caught:
        await crawls.main()
    assert caught.value is failure
    engine.dispose.assert_awaited_once()


@pytest.mark.parametrize("signal_requested_first", [False, True])
async def test_actual_caller_cancellation_is_not_hidden_by_signal_stop(monkeypatch, signal_requested_first):
    loop = asyncio.get_running_loop()
    handlers = {}
    restored = []
    started, unwinding, release = asyncio.Event(), asyncio.Event(), asyncio.Event()
    engine = SimpleNamespace(dispose=AsyncMock())
    monkeypatch.setattr(loop, "add_signal_handler", lambda sig, callback: handlers.update({sig: callback}))
    monkeypatch.setattr(loop, "remove_signal_handler", lambda *_args: None)
    monkeypatch.setattr(crawls.signal, "signal", lambda sig, _previous: restored.append(sig))
    monkeypatch.setattr(
        crawls, "load", lambda _model: SimpleNamespace(config_dir=None, app_db=SimpleNamespace(dsn=None))
    )
    monkeypatch.setattr(crawls, "definitions", lambda _directory: None)
    monkeypatch.setattr(crawls, "make_engine", lambda *_args: engine)

    async def run(_self):
        started.set()
        try:
            await asyncio.Event().wait()
        finally:
            unwinding.set()
            await release.wait()

    monkeypatch.setattr(crawls.Crawler, "run", run)
    task = asyncio.create_task(crawls.main())
    await started.wait()
    if signal_requested_first:
        handlers[signal.SIGTERM]()
        await unwinding.wait()
    task.cancel()
    await unwinding.wait()
    release.set()
    with pytest.raises(asyncio.CancelledError):
        await task
    engine.dispose.assert_awaited_once()
    assert restored == [signal.SIGTERM, signal.SIGINT]


async def test_cancelled_physical_request_kills_and_reaps_child(monkeypatch):
    started = asyncio.Event()
    process = SimpleNamespace(returncode=None, wait=AsyncMock(), kill=Mock())

    async def communicate(_payload):
        started.set()
        await asyncio.Event().wait()

    process.communicate = communicate

    @asynccontextmanager
    async def transaction(_engine):
        yield SimpleNamespace(execute=AsyncMock(), scalar=AsyncMock(return_value=True))

    monkeypatch.setattr(crawls, "system_tx", transaction)
    monkeypatch.setattr(crawls.asyncio, "create_subprocess_exec", AsyncMock(return_value=process))
    cfg = SimpleNamespace(
        board_client=SimpleNamespace(internal_url="http://owned.test"),
        crawl=SimpleNamespace(
            domain_delay_s=0,
            owned_origin_private_access=False,
            timeout_s=1,
            max_response_bytes=1024,
            user_agent="test-crawler",
            request_budget_s=1,
        ),
    )
    crawler = crawls.Crawler(cfg, None)
    task = asyncio.create_task(crawler.request("/owned", "owned_board"))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    process.kill.assert_called_once()
    process.wait.assert_awaited_once()


async def test_cancelled_job_clears_robots_without_false_finish():
    started = asyncio.Event()
    crawler = crawls.Crawler(SimpleNamespace(), None)
    job = {"id": uuid4()}
    crawler._robots[job["id"]] = None

    async def page(_tenant, _job):
        started.set()
        await asyncio.Event().wait()

    crawler.page = page
    crawler.finish = AsyncMock()
    task = asyncio.create_task(crawler.run_job(uuid4(), job))
    await started.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    crawler.finish.assert_not_awaited()
    assert job["id"] not in crawler._robots
