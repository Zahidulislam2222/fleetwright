"""Phase 4 exit criteria, against a real mock board, real Chromium and the real database:
slots sign in with emailed OTP; sessions are sealed in the vault and reused after a restart without
a new code; a revoked session is detected and replaced; the captcha step pauses and resumes; a
failed sign-in leaves a trace and a screenshot; logs never contain passwords, codes or cookies;
heartbeats flow and draining releases every account."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from playwright.async_api import Browser, async_playwright
from sqlalchemy import text

from boardkit import Board
from dbkit import Db
from fw_browser.otp import extract_code
from fw_core.db import tenant_tx
from fw_core.logs import JsonFormatter
from workerkit import board_tenant, mailpit_count, running_fleet, wait_for

pytestmark = [pytest.mark.integration, pytest.mark.browser]


@pytest.fixture(scope="session")
async def browser() -> AsyncIterator[Browser]:
    async with async_playwright() as pw:
        b = await pw.chromium.launch()
        yield b
        await b.close()


async def test_sign_in_heartbeat_restart_without_new_otp_and_drain(
    db: Db, board: Board, browser: Browser, tmp_path: Path
) -> None:
    tenant = await board_tenant(db, board, 3)
    emails = [f"{u}@{board.settings.board.email_domain}" for u, _ in tenant.accounts.values()]
    async with running_fleet(db, board, browser, tenant.cell, tmp_path) as fleet:
        await wait_for(lambda: all(s.state == "ready" for s in fleet.slots), 60, "all slots signed in")
        assert sorted(s.role for s in fleet.slots) == ["claimer", "claimer", "watcher"]
        assert {s.account.id for s in fleet.slots if s.account} == set(tenant.accounts)
        assert all(s.sign_ins == 1 for s in fleet.slots)
        async with tenant_tx(db.app, tenant.id) as conn:
            first_beat = dict((await conn.execute(text("SELECT id, heartbeat_at FROM workers"))).all())  # type: ignore[arg-type]
        await wait_for(lambda: fleet.memory_mb > 0, 5, "memory measured")
        await asyncio.sleep(1.2)
        async with tenant_tx(db.app, tenant.id) as conn:
            beats = (await conn.execute(text("SELECT id, heartbeat_at, memory_mb, state FROM workers"))).all()
            sessions = (await conn.execute(text("SELECT state, sealed FROM account_sessions"))).all()
            held = (
                await conn.execute(text("SELECT count(*) FROM accounts WHERE holder_worker IS NOT NULL"))
            ).scalar_one()
        assert len(beats) == 3 and all(b.heartbeat_at > first_beat[b.id] for b in beats), "heartbeats advance"
        assert all(b.memory_mb and b.memory_mb > 0 and b.state == "running" for b in beats)
        assert [s.state for s in sessions] == ["fresh"] * 3 and held == 3
        cookie_values = [
            c["value"].encode() for s in fleet.slots if s.session for c in s.session.storage_state["cookies"]
        ]
        assert cookie_values and not any(v in s.sealed for v in cookie_values for s in sessions), "vault is sealed"
        codes_sent = [mailpit_count(board, e) for e in emails]
    async with tenant_tx(db.app, tenant.id) as conn:
        assert (
            await conn.execute(text("SELECT count(*) FROM accounts WHERE holder_worker IS NOT NULL"))
        ).scalar_one() == 0
        assert {r.state for r in await conn.execute(text("SELECT state FROM workers"))} == {"stopped"}

    # a new process: sessions come back from the vault, no new one-time code is requested
    async with running_fleet(db, board, browser, tenant.cell, tmp_path) as fleet:
        await wait_for(lambda: all(s.state == "ready" for s in fleet.slots), 30, "slots restored")
        assert all(s.sign_ins == 0 and s.restores == 1 for s in fleet.slots)
        assert [mailpit_count(board, e) for e in emails] == codes_sent


async def test_revoked_session_is_replaced(db: Db, board: Board, browser: Browser, tmp_path: Path) -> None:
    tenant = await board_tenant(db, board, 1)
    async with running_fleet(db, board, browser, tenant.cell, tmp_path, contexts=1) as fleet:
        slot = fleet.slots[0]
        await wait_for(lambda: slot.state == "ready", 60, "signed in")
        ((username, _),) = tenant.accounts.values()
        assert board.admin.post("/admin/sessions/expire", json={"username": username}).json()["revoked"] >= 1
        await wait_for(lambda: slot.sign_ins == 2 and slot.state == "ready", 60, "signed in again")
        assert slot.last_error is None
        assert not list(tmp_path.rglob("trace.zip")), "an expired session is routine, not evidence"


async def test_captcha_pauses_and_resumes(db: Db, board: Board, browser: Browser, tmp_path: Path) -> None:
    tenant = await board_tenant(db, board, 1)
    board.admin.patch("/admin/settings", json={"captcha_enabled": True, "captcha_after_requests": 5}).raise_for_status()
    await asyncio.sleep(1.1)  # the board caches rules for up to 1 s
    async with running_fleet(db, board, browser, tenant.cell, tmp_path, contexts=1) as fleet:
        slot = fleet.slots[0]
        await wait_for(lambda: slot.captchas >= 2, 60, "captcha solved repeatedly")
        assert slot.state == "ready" and slot.last_error is None


async def test_failed_sign_in_leaves_evidence_and_logs_hold_no_secrets(
    db: Db, board: Board, browser: Browser, tmp_path: Path, caplog: pytest.LogCaptureFixture
) -> None:
    tenant = await board_tenant(db, board, 2, wrong_password={1})
    caplog.set_level(logging.DEBUG)
    async with running_fleet(db, board, browser, tenant.cell, tmp_path, contexts=2, watchers=0) as fleet:
        good_id = next(iter(tenant.accounts))
        await wait_for(lambda: any(s.account and s.account.id == good_id for s in fleet.slots), 30, "accounts held")
        good = next(s for s in fleet.slots if s.account and s.account.id == good_id)
        await wait_for(lambda: good.state == "ready", 60, "good account signed in")
        await wait_for(lambda: any(tmp_path.rglob("trace.zip")), 60, "evidence for the failed sign-in")
        bad = next(s for s in fleet.slots if s is not good)
        assert bad.last_error == "SignInFailed"
        cookies = [c["value"] for c in good.session.storage_state["cookies"]] if good.session else []
    folder = next(tmp_path.rglob("trace.zip")).parent
    assert (folder / "screenshot.png").stat().st_size > 0 and (folder / "trace.zip").stat().st_size > 0
    assert str(tenant.id) in str(folder) and "sign-in" in folder.name

    (good_user, good_pw), (_, bad_pw) = tenant.accounts.values()
    code = _latest_code(board, f"{good_user}@{board.settings.board.email_domain}")
    formatter = JsonFormatter("worker")
    logged = "\n".join(formatter.format(r) for r in caplog.records)
    assert "signed in" in logged
    secrets_ = [good_pw, bad_pw, bad_pw + "-wrong", code, *cookies]
    leaked = [s for s in secrets_ if s and s in logged]
    assert not leaked, f"{len(leaked)} secret value(s) appeared in the logs"


def _latest_code(board: Board, address: str) -> str:
    found = httpx.get(
        f"{board.settings.mailpit.api_url}/api/v1/search", params={"query": f'to:"{address}"'}, timeout=10
    ).json()["messages"]
    code = extract_code(found[0]["Snippet"])
    assert code is not None
    return code


def test_events_carry_no_secrets() -> None:
    """Event payloads are built from ids and states only (static check on the emit call sites)."""
    source = (Path(__file__).resolve().parents[1] / "src" / "fw_worker" / "runtime.py").read_text(encoding="utf-8")
    calls = [line for line in source.splitlines() if "emit(" in line and "def emit" not in line]
    assert calls
    assert not any(word in line for line in calls for word in ("password", "code", "cookie", "storage_state")), calls
    assert json.dumps({"ok": True})


async def test_slot_that_loses_its_account_hold_stops_using_it(
    db: Db, board: Board, browser: Browser, tmp_path: Path
) -> None:
    tenant = await board_tenant(db, board, 1)
    async with running_fleet(db, board, browser, tenant.cell, tmp_path, contexts=1) as fleet:
        slot = fleet.slots[0]
        await wait_for(lambda: slot.state == "ready", 60, "signed in")
        async with tenant_tx(db.app, tenant.id) as conn:  # another holder takes the account over
            await conn.execute(
                text(
                    "UPDATE accounts SET holder_worker = 'intruder', holder_expires_at = clock_timestamp() + interval '1 hour'"
                )
            )
        await wait_for(lambda: slot.account is None and slot.context is None, 10, "slot dropped the account")
        async with tenant_tx(db.app, tenant.id) as conn:
            await conn.execute(text("UPDATE accounts SET holder_worker = NULL, holder_expires_at = NULL"))
        await wait_for(lambda: slot.account is not None and slot.state == "ready", 30, "slot took the account back")
        assert slot.sign_ins == 1 and slot.restores == 1, "the vault session was reused, no new one-time code"
