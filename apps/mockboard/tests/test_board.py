"""Phase 2 exit criteria: login with emailed OTP, booking, double-booking detection, and one test per
adversity toggle. Runs against a real board process, Postgres and Mailpit (local Compose stack)."""

from __future__ import annotations

import asyncio
import re
import secrets
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import httpx
import pytest

from boardkit import Board
from fw_browser.otp import MailpitOtp

pytestmark = pytest.mark.integration


def db_now(board: Board) -> str:
    """Start times come from the database clock: the Docker VM clock can lag the host clock by
    hundreds of milliseconds, and every ground-truth timestamp is a database timestamp."""
    return str(httpx.get(f"{board.url}/healthz").json()["db_time"])


async def make_account(board: Board) -> tuple[str, str]:
    username = f"carrier-{secrets.token_hex(4)}"
    password = secrets.token_urlsafe(18)
    board.admin.post("/admin/accounts", json={"username": username, "password": password}).raise_for_status()
    return username, password


async def sign_in(board: Board, username: str, password: str) -> httpx.AsyncClient:
    client = httpx.AsyncClient(base_url=board.url, timeout=15, follow_redirects=False)
    since = datetime.now(UTC)
    res = await client.post("/login", data={"username": username, "password": password})
    assert res.status_code == 303 and res.headers["location"] == "/otp"
    otp = MailpitOtp(board.settings.mailpit.api_url)
    try:
        code = await otp.wait_for_code(f"{username}@{board.settings.board.email_domain}", since, 15)
    finally:
        await otp.aclose()
    res = await client.post("/otp", data={"code": code})
    assert res.status_code == 303 and res.headers["location"] == "/loads"
    return client


@pytest.fixture
async def carrier(board: Board) -> AsyncIterator[httpx.AsyncClient]:
    client = await sign_in(board, *await make_account(board))
    yield client
    await client.aclose()


async def csrf(client: httpx.AsyncClient) -> str:
    res = await client.get("/api/me")
    res.raise_for_status()
    return str(res.json()["csrf"])


async def next_open(client: httpx.AsyncClient, timeout_s: float = 10) -> dict[str, object]:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        res = await client.get("/api/loads")
        if res.status_code == 200:
            open_loads = [load for load in res.json()["loads"] if load["status"] == "open"]
            if open_loads:
                return dict(open_loads[-1])
        await asyncio.sleep(0.2)
    raise AssertionError("no open load appeared")


async def next_open_load(client: httpx.AsyncClient, timeout_s: float = 10) -> str:
    return str((await next_open(client, timeout_s))["ref"])


async def test_login_with_emailed_otp_then_book_and_detect_double_booking(
    board: Board, carrier: httpx.AsyncClient
) -> None:
    started = db_now(board)
    token = await csrf(carrier)
    ref = await next_open_load(carrier)
    first = await carrier.post(f"/api/loads/{ref}/book", headers={"X-CSRF-Token": token})
    assert first.status_code == 200 and first.json()["status"] == "booked"
    second = await carrier.post(f"/api/loads/{ref}/book", headers={"X-CSRF-Token": token})
    assert second.status_code == 409 and second.json() == {"status": "already_booked", "ref": ref, "by_you": True}
    bookings = (await carrier.get("/api/bookings")).json()["bookings"]
    assert ref in [b["ref"] for b in bookings]
    audit = board.admin.get("/admin/audit/duplicates", params={"since": started}).json()
    duplicate = [d for d in audit["duplicate_loads"] if d["ref"] == ref]
    assert duplicate and duplicate[0]["attempts"] == 2, (ref, started, audit)


async def test_second_account_cannot_take_a_booked_load(board: Board, carrier: httpx.AsyncClient) -> None:
    other = await sign_in(board, *await make_account(board))
    try:
        ref = await next_open_load(carrier)
        assert (
            await carrier.post(f"/api/loads/{ref}/book", headers={"X-CSRF-Token": await csrf(carrier)})
        ).status_code == 200
        lost = await other.post(f"/api/loads/{ref}/book", headers={"X-CSRF-Token": await csrf(other)})
        assert lost.status_code == 409 and lost.json()["by_you"] is False
    finally:
        await other.aclose()


async def test_wrong_password_and_wrong_code_are_refused(board: Board) -> None:
    username, password = await make_account(board)
    async with httpx.AsyncClient(base_url=board.url, follow_redirects=False) as client:
        res = await client.post("/login", data={"username": username, "password": password + "x"})
        assert res.headers["location"] == "/login?error=credentials"
        res = await client.post("/login", data={"username": "nobody-here", "password": "whatever-password"})
        assert res.headers["location"] == "/login?error=credentials"
        await client.post("/login", data={"username": username, "password": password})
        for _ in range(5):
            res = await client.post("/otp", data={"code": "000000x"})
            assert res.headers["location"] == "/otp?error=code"
        res = await client.post("/otp", data={"code": "000000x"})
        assert res.headers["location"] == "/login?error=expired", "challenge must die after 5 wrong codes"


async def test_csrf_token_is_required_for_booking(carrier: httpx.AsyncClient) -> None:
    ref = await next_open_load(carrier)
    assert (await carrier.post(f"/api/loads/{ref}/book")).status_code == 403
    assert (await carrier.post(f"/api/loads/{ref}/book", headers={"X-CSRF-Token": "wrong"})).status_code == 403


async def test_admin_settings_reject_unknown_switches(board: Board) -> None:
    res = board.admin.patch("/admin/settings", json={"no_such_switch": True})
    assert res.status_code == 422


async def test_admin_api_requires_the_token(board: Board) -> None:
    assert httpx.get(f"{board.url}/admin/settings").status_code == 401
    assert httpx.get(f"{board.url}/admin/settings", headers={"Authorization": "Bearer nope"}).status_code == 401


# ---------------- adversity toggles ----------------


def set_rules(board: Board, **rules: object) -> None:
    board.admin.patch("/admin/settings", json=rules).raise_for_status()
    time.sleep(1.1)  # rules are cached for up to 1 s per board instance


async def test_rate_limit_toggle_returns_429(board: Board, carrier: httpx.AsyncClient) -> None:
    set_rules(board, rate_limit_per_min=3)
    codes = [(await carrier.get("/api/loads")).status_code for _ in range(6)]
    assert 429 in codes, codes
    res = await carrier.get("/api/loads")
    assert res.status_code == 429 and res.headers["retry-after"] == "60"


async def test_error_rate_toggle_returns_5xx(board: Board, carrier: httpx.AsyncClient) -> None:
    set_rules(board, error_rate=1.0)
    assert (await carrier.get("/api/loads")).status_code == 503


async def test_slow_toggle_delays_responses(board: Board, carrier: httpx.AsyncClient) -> None:
    set_rules(board, slow_rate=1.0, slow_ms=700)
    started = time.monotonic()
    assert (await carrier.get("/api/loads")).status_code == 200
    assert time.monotonic() - started >= 0.7


async def test_ack_loss_toggle_keeps_the_booking_but_answers_500(board: Board, carrier: httpx.AsyncClient) -> None:
    load = await next_open(carrier)
    ref = str(load["ref"])
    set_rules(board, ack_loss_rate=1.0)
    res = await carrier.post(f"/api/loads/{ref}/book", headers={"X-CSRF-Token": await csrf(carrier)})
    assert res.status_code == 500
    assert ref in [b["ref"] for b in (await carrier.get("/api/bookings")).json()["bookings"]], "booking must stand"
    # Times are reported to the millisecond, so neighbours from the same millisecond can come back too.
    truth = board.admin.get("/admin/ground-truth", params={"since": load["published_at"], "limit": 50}).json()["loads"]
    mine = [item for item in truth if item["ref"] == ref]
    assert mine and [a["outcome"] for a in mine[0]["attempts"]] == ["ack_lost"]


async def test_layout_toggle_changes_the_page_structure(board: Board, carrier: httpx.AsyncClient) -> None:
    normal = (await carrier.get("/loads")).text
    assert 'id="loads-table"' in normal and 'id="offers"' not in normal
    set_rules(board, layout_variant="b")
    changed = (await carrier.get("/loads")).text
    assert 'id="offers"' in changed and 'id="loads-table"' not in changed


async def test_competitor_bots_book_loads(board: Board) -> None:
    started = db_now(board)
    set_rules(board, competitor_share=1.0, competitor_delay_ms={"lo": 50, "hi": 150})
    await asyncio.sleep(3)
    truth = board.admin.get("/admin/ground-truth", params={"since": started}).json()["loads"]
    rivals = [item for item in truth if item["booked_by"] and item["booked_by"].startswith("rival")]
    assert len(rivals) >= 5, f"expected rival bookings, got {len(rivals)} of {len(truth)}"


async def test_forced_session_expiry(board: Board, carrier: httpx.AsyncClient) -> None:
    assert (await carrier.get("/api/me")).status_code == 200
    board.admin.post("/admin/sessions/expire", json={}).raise_for_status()
    assert (await carrier.get("/api/me")).status_code == 401


async def test_single_session_toggle_revokes_the_first_login(board: Board) -> None:
    set_rules(board, single_session=True)
    username, password = await make_account(board)
    first = await sign_in(board, username, password)
    second = await sign_in(board, username, password)
    try:
        assert (await second.get("/api/me")).status_code == 200
        assert (await first.get("/api/me")).status_code == 401
    finally:
        await first.aclose()
        await second.aclose()


async def test_captcha_after_too_many_requests_and_solving_it(board: Board, carrier: httpx.AsyncClient) -> None:
    set_rules(board, captcha_after_requests=5)
    codes = [(await carrier.get("/api/loads")).status_code for _ in range(7)]
    assert codes[-1] == 403
    blocked = await carrier.get("/api/loads")
    assert blocked.status_code == 403 and blocked.json()["detail"]["captcha_required"] is True
    page = (await carrier.get("/captcha")).text
    a = int(re.search(r'id="captcha-a">(\d+)<', page).group(1))  # type: ignore[union-attr]
    b = int(re.search(r'id="captcha-b">(\d+)<', page).group(1))  # type: ignore[union-attr]
    wrong = await carrier.post("/captcha", data={"answer": str(a + b + 1)})
    assert wrong.headers["location"] == "/captcha?error=wrong"
    page = (await carrier.get("/captcha")).text  # the question stays the same until it is solved
    assert f'id="captcha-a">{a}<' in page
    solved = await carrier.post("/captcha", data={"answer": str(a + b)})
    assert solved.headers["location"] == "/loads"
    assert (await carrier.get("/api/loads")).status_code == 200


async def test_feed_reaches_100_loads_per_second(board: Board) -> None:
    """Scale check: the feed can stress a fleet (6000/min = 100/s)."""
    started = db_now(board)
    set_rules(board, feed_rate_per_min=6000)
    await asyncio.sleep(3)
    set_rules(board, feed_rate_per_min=600)
    audit = board.admin.get("/admin/audit/duplicates", params={"since": started}).json()
    # About 4 s at 100/s (3 s plus the rule cache); allow scheduler jitter.
    assert audit["loads_published"] >= 300, audit["loads_published"]


async def test_public_watch_feed_needs_no_login(board: Board) -> None:
    res = httpx.get(f"{board.url}/api/public/recent")
    assert res.status_code == 200 and "loads" in res.json()
    assert httpx.get(f"{board.url}/watch").status_code == 200
    page = httpx.get(f"{board.url}/watch")
    assert "default-src 'self'" in page.headers["content-security-policy"]
