"""Slot behaviours (Phase 5).

watcher: keeps the target's feed page open and listens to the page's own feed responses
(`page.on("response")`), so it works whatever the page layout looks like. Every open job goes to
the tenant's `detected` stream with the time it was seen, corrected to the database clock.

claimer: takes claim messages from the tenant's `act` stream, leases the claim with its account
(fencing token), moves it to ACTING only while the lease is current, performs the action once, and
records what it observed. It never retries an action whose result it does not know: that claim
becomes UNKNOWN and the reconciler asks the target."""

from __future__ import annotations

import asyncio
import contextlib
import fnmatch
import json
import logging
from collections import OrderedDict
from datetime import datetime
from typing import Any
from urllib.parse import quote, urlsplit
from uuid import UUID

from playwright.async_api import APIResponse, Locator, Response
from playwright.async_api import Error as PlaywrightError

from fw_core import claims
from fw_core.db import tenant_tx
from fw_core.targets import TargetSpec
from fw_queue import keys, streams
from fw_worker.runtime import Slot

log = logging.getLogger(__name__)

RECENT_JOBS = 20_000  # per watcher: job keys already sent (the feed repeats recent jobs on reload)
KEEPALIVE_EVERY = 5  # idle rounds between session checks
RECLAIM_EVERY = 10  # idle rounds between reclaiming messages from dead consumers
BODY_NEEDED = frozenset({403, 409})  # statuses whose meaning depends on the body


def _matches(url: str, pattern: str) -> bool:
    return fnmatch.fnmatchcase(url.split("?", 1)[0], pattern)


def _spec(slot: Slot) -> tuple[TargetSpec, str]:
    assert slot.account is not None
    return slot.fleet.targets.get(slot.account.target), slot.fleet.base_urls[slot.account.target]


# ---------------- watcher ----------------


async def watch(slot: Slot) -> None:
    assert slot.page is not None
    spec, base = _spec(slot)
    feed_path = urlsplit(base + spec.api.loads).path
    stream = keys.detected_stream(slot.tenant_id)
    arrived: asyncio.Queue[tuple[Response, datetime]] = asyncio.Queue(maxsize=1000)
    sent: OrderedDict[str, None] = OrderedDict()
    page = slot.page

    def on_response(response: Response) -> None:
        if response.status == 200 and urlsplit(response.url).path == feed_path:
            with contextlib.suppress(asyncio.QueueFull):
                arrived.put_nowait((response, slot.fleet.db_now()))

    page.on("response", on_response)
    try:
        if not _matches(page.url, spec.login.home_url):
            await page.goto(base + spec.feed_page)
        idle = 0
        while not slot.due_for_attention():
            try:
                response, seen = await asyncio.wait_for(arrived.get(), slot.cfg.heartbeat_s)
            except TimeoutError:
                idle += 1
                if _matches(page.url, spec.captcha.url):
                    await slot.solve_captcha()
                    await page.goto(base + spec.feed_page)
                elif not _matches(page.url, spec.login.home_url) or idle % KEEPALIVE_EVERY == 0:
                    await slot.keep_alive()
                    if slot.session is not None and not _matches(page.url, spec.login.home_url):
                        await page.goto(base + spec.feed_page)
                continue
            idle = 0
            body = await bounded_json(response, slot.cfg.action_timeout_ms)
            if body is None:  # body unreadable (page moved on) or never delivered
                continue
            for job in body.get("loads", []):
                ref = str(job.get("ref", ""))
                if not ref or job.get("status") != "open" or ref in sent:
                    continue
                sent[ref] = None
                if len(sent) > RECENT_JOBS:
                    sent.popitem(last=False)
                await streams.add(
                    slot.fleet.stream,
                    stream,
                    {
                        "key": ref,
                        "job": json.dumps(job, separators=(",", ":")),
                        "published_at": str(job.get("published_at") or ""),
                        "seen_at": seen.isoformat(),
                        "offset_ms": "" if slot.fleet.clock_offset_ms is None else f"{slot.fleet.clock_offset_ms:.3f}",
                        "watcher": slot.id,
                    },
                    slot.fleet.claims_cfg.stream_maxlen,
                )
                slot.actions += 1
    finally:
        page.remove_listener("response", on_response)


# ---------------- claimer ----------------


async def claim(slot: Slot) -> None:
    fleet = slot.fleet
    stream = keys.act_stream(slot.tenant_id)
    await streams.ensure_group(fleet.stream, stream, keys.ACTOR_GROUP)
    block_ms = int(slot.cfg.heartbeat_s * 1000)
    idle = 0
    while not slot.due_for_attention():
        batch = await streams.read(fleet.stream, [stream], keys.ACTOR_GROUP, slot.id, 1, block_ms)
        if not batch:
            idle += 1
            if idle % RECLAIM_EVERY == 0:
                batch = await streams.reclaim(
                    fleet.stream,
                    stream,
                    keys.ACTOR_GROUP,
                    slot.id,
                    fleet.claims_cfg.autoclaim_idle_ms,
                    1,
                    fleet.claims_cfg.max_deliveries,
                )
            if not batch:
                if idle % KEEPALIVE_EVERY == 0:
                    await slot.keep_alive()
                continue
        idle = 0
        for msg in batch:
            if await act_on(slot, UUID(msg.fields["claim_id"])):
                await streams.ack(fleet.stream, msg, keys.ACTOR_GROUP)


async def act_on(slot: Slot, claim_id: UUID) -> bool:
    """Returns True when the message is finished with (ack), False to leave it for another
    consumer (this account still holds another lease)."""
    fleet, account, cc = slot.fleet, slot.account, slot.fleet.claims_cfg
    assert account is not None
    try:
        async with tenant_tx(fleet.engine, slot.tenant_id) as conn:
            held = await claims.lease(
                conn,
                slot.tenant_id,
                claim_id,
                worker_id=slot.id,
                account_id=account.id,
                ttl_ms=cc.lease_ttl_ms,
                max_age_s=cc.queued_max_age_s,
            )
    except claims.AccountBusy:
        return False
    if held is None:  # someone else won it, or it is no longer QUEUED
        return True
    # Everything that sends nothing (finding the job on the page, fetching the anti-forgery token)
    # happens before ACTING, so the ACTING window holds only the action and its answer.
    button = await locate(slot, held.target_job_key) if slot.cfg.action_mode == "click" else None
    if slot.csrf is None:
        slot.csrf = await _csrf(slot, *_spec(slot))
    async with tenant_tx(fleet.engine, slot.tenant_id) as conn:
        acting = await claims.start_acting(conn, slot.tenant_id, held, slot.id, cc.lease_ttl_ms)
    if not acting:
        return True
    outcome: claims.Outcome
    if slot.cfg.action_mode == "click" and button is None:
        outcome, note = "failed", "job not on the page; nothing was sent"
    else:
        outcome, note = await perform(slot, held.target_job_key, button)
    async with tenant_tx(fleet.engine, slot.tenant_id) as conn:
        state = await claims.finish(conn, slot.tenant_id, held, slot.id, outcome, note)
    slot.actions += 1
    await fleet.emit(
        slot.tenant_id,
        {
            "type": "claim",
            "state": state,
            "claim_id": claim_id,
            "key": held.target_job_key,
            "slot": slot.id,
            "note": note,
        },
    )
    return True


async def locate(slot: Slot, key: str) -> Locator | None:
    """Click mode: the job's book button on the feed page, or None if it is not there in time."""
    page = slot.page
    assert page is not None
    spec, base = _spec(slot)
    if _matches(page.url, spec.captcha.url):
        await slot.solve_captcha()
    if not _matches(page.url, spec.login.home_url):
        await page.goto(base + spec.feed_page)
    button = page.locator(spec.click.book_button.format(ref=key))
    try:
        await button.wait_for(state="visible", timeout=slot.cfg.action_timeout_ms)
    except PlaywrightError:
        return None
    return button


async def perform(slot: Slot, key: str, button: Locator | None = None) -> tuple[claims.Outcome, str]:
    """The single action. 'unknown' whenever the request may have reached the target and no
    definite answer came back."""
    spec, base = _spec(slot)
    url = base + spec.api.book.format(ref=quote(key, safe=""))
    if button is not None:
        return await _click(slot, spec, button, url)
    assert slot.context is not None
    try:
        reply = await slot.context.request.post(
            url,
            headers={spec.api.csrf_header: slot.csrf or ""},
            timeout=slot.cfg.action_timeout_ms,
            fail_on_status_code=False,
        )
    except PlaywrightError:
        return "unknown", "no answer from the target"
    return await _interpret(slot, spec, reply.status, await _body(reply))


async def _click(slot: Slot, spec: TargetSpec, button: Locator, url: str) -> tuple[claims.Outcome, str]:
    page = slot.page
    assert page is not None
    book_path = urlsplit(url).path
    try:
        async with page.expect_response(
            lambda r: urlsplit(r.url).path == book_path and r.request.method == "POST",
            timeout=slot.cfg.action_timeout_ms,
        ) as info:
            await button.click(timeout=slot.cfg.action_timeout_ms)
        response = await info.value
    except PlaywrightError:
        return "unknown", "clicked, no answer seen"
    # Read the body only when the status alone is not enough: page-response bodies can be slow or
    # unavailable once the page's own script has consumed them.
    body = await bounded_json(response, slot.cfg.action_timeout_ms) if response.status in BODY_NEEDED else {}
    return await _interpret(slot, spec, response.status, body)


async def _interpret(
    slot: Slot, spec: TargetSpec, status: int, body: dict[str, Any] | None
) -> tuple[claims.Outcome, str]:
    """`body` None = the answer's body could not be read; never guess from it."""
    assert slot.account is not None
    blocked = status in spec.blocked_statuses
    slot.fleet.proxies.record(str(slot.account.id), blocked, asyncio.get_running_loop().time())
    if 200 <= status < 300:
        return "confirmed", "booked"
    if status == 409:
        if body is None:
            return "unknown", "taken, but whether by us is unreadable"
        return (
            ("confirmed", "already booked by this account")
            if body.get("by_you")
            else ("failed", "taken by someone else")
        )
    if status == 404:
        return "failed", "job no longer exists"
    if status == 401:
        slot.session = None  # signs in again before its next message
        return "failed", "session rejected before booking"
    if status == 403 and "captcha" in json.dumps(body or {}):
        with contextlib.suppress(Exception):
            await slot.solve_captcha()
        return "failed", "captcha before booking"
    if status == 403:
        slot.csrf = None
        return "failed", "request rejected (403)"
    if status == 429:
        return "failed", "rate limited before booking"
    return "unknown", f"target answered {status}"


async def _csrf(slot: Slot, spec: TargetSpec, base: str) -> str | None:
    assert slot.context is not None
    reply = await slot.context.request.get(base + spec.api.me, timeout=slot.cfg.action_timeout_ms)
    if not reply.ok:
        return None
    return str((await reply.json()).get("csrf") or "") or None


async def _body(reply: APIResponse) -> dict[str, Any] | None:
    try:
        data = await reply.json()
    except (PlaywrightError, ValueError):
        return None
    return data if isinstance(data, dict) else {"detail": data}


async def bounded_json(response: Response, timeout_ms: int) -> dict[str, Any] | None:
    """A page response's JSON body, or None. Playwright's Response.json() has no timeout and was
    seen to wait forever for the body of a response the page's own script had consumed."""
    try:
        data = await asyncio.wait_for(response.json(), timeout_ms / 1000)
    except (TimeoutError, PlaywrightError, ValueError):
        return None
    return data if isinstance(data, dict) else {"detail": data}
