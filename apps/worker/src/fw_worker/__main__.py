"""Worker process entry point: `python -m fw_worker`. Stops cleanly on SIGTERM/SIGINT (drain)."""

from __future__ import annotations

import asyncio
import contextlib
import logging
import signal
from collections.abc import Awaitable, Callable
from datetime import date

from playwright.async_api import Browser, async_playwright

from fw_browser.evidence import EvidenceStore
from fw_browser.otp import MailpitOtp
from fw_browser.profiles import load_profiles
from fw_browser.proxy import ProxyPool, load_proxy_config
from fw_core.crypto import Envelope
from fw_core.db import make_engine
from fw_core.logs import setup_logging
from fw_core.settings import WorkerAppSettings, load
from fw_core.targets import load_targets
from fw_core.vault import Vault
from fw_queue import client
from fw_worker.behaviours import claim, watch
from fw_worker.runtime import Behaviour, Fleet, Role

log = logging.getLogger("fw_worker")
EVIDENCE_PRUNE_S = 3600.0  # housekeeping cadence, not a tuning knob


def build_fleet(cfg: WorkerAppSettings, browser: Browser, behaviours: dict[Role, Behaviour]) -> Fleet:
    return Fleet(
        cfg=cfg.worker,
        claims_cfg=cfg.claims,
        engine=make_engine(cfg.worker_db.dsn, cfg.worker_db, f"fw-worker-{cfg.worker.cell}"),
        events=client.core(cfg.redis),
        stream=client.cell(cfg.redis, cfg.worker.cell, block_ms=int(cfg.worker.heartbeat_s * 1000)),
        browser=browser,
        vault=Vault(Envelope(cfg.vault.master_key_b64.get_secret_value(), cfg.vault.key_id)),
        targets=load_targets(cfg.config_dir),
        base_urls={"demo-board": cfg.board_client.internal_url},
        profiles=load_profiles(cfg.config_dir),
        proxies=ProxyPool(load_proxy_config(cfg.config_dir)),
        evidence=EvidenceStore(cfg.storage.local_dir, cfg.storage.retention_days),
        email_otp=MailpitOtp(cfg.mailpit.api_url),
        behaviours=behaviours,
    )


async def main() -> None:
    cfg = load(WorkerAppSettings)
    setup_logging("worker", cfg.log_level)
    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        with contextlib.suppress(NotImplementedError):  # Windows has no loop signal handlers
            loop.add_signal_handler(sig, stop.set)
    async with async_playwright() as pw:
        browser = await pw.chromium.launch(headless=cfg.worker.headless)
        fleet = build_fleet(cfg, browser, {"watcher": watch, "claimer": claim})
        disconnected = asyncio.Event()

        def on_disconnect(_browser: Browser) -> None:
            if not stop.is_set():
                disconnected.set()
                stop.set()

        browser.on("disconnected", on_disconnect)
        failure: BaseException | None = None
        try:
            await fleet.start()
            next_prune = loop.time()
            while not stop.is_set():
                # Driver EOF does not necessarily emit Browser.disconnected. A bounded,
                # read-only Chromium round trip also detects a dead driver transport.
                try:
                    async with asyncio.timeout(cfg.worker.action_timeout_ms / 1000):
                        session = await browser.new_browser_cdp_session()
                        await session.send("Browser.getVersion")
                        await session.detach()
                        # On failure the whole browser is disposed below. Do not await detach
                        # in a finally block after this deadline has already cancelled send.
                except Exception:
                    disconnected.set()
                    stop.set()
                    break
                if loop.time() >= next_prune:
                    fleet.evidence.prune(date.today())
                    next_prune = loop.time() + EVIDENCE_PRUNE_S
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(stop.wait(), cfg.worker.heartbeat_s)
        except BaseException as error:
            failure = error
        finally:
            stop.set()
            browser.remove_listener("disconnected", on_disconnect)
            if failure is None and disconnected.is_set():
                failure = RuntimeError("browser disconnected; exiting for supervised recovery")
            cleanups: list[Callable[[], Awaitable[object]]] = [
                fleet.drain,
                fleet.engine.dispose,
                fleet.events.aclose,
                fleet.stream.aclose,
            ]
            close_otp = getattr(fleet.email_otp, "aclose", None)
            if close_otp is not None:
                cleanups.append(close_otp)
            if browser.is_connected():

                async def close_browser() -> None:
                    await asyncio.wait_for(browser.close(), cfg.worker.action_timeout_ms / 1000)

                cleanups.append(close_browser)
            failures: list[Exception] = []
            for cleanup in cleanups:
                try:
                    await cleanup()
                except Exception as error:
                    failures.append(error)
            if failure is not None:
                if failures:
                    raise failure from ExceptionGroup("worker cleanup failures", failures)
                raise failure
            if failures:
                raise failures[0] from (
                    ExceptionGroup("worker cleanup failures", failures[1:]) if len(failures) > 1 else None
                )


if __name__ == "__main__":
    with contextlib.suppress(KeyboardInterrupt):
        asyncio.run(main())
