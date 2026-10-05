"""The console API against the real database, Redis and mock board: sign-in with a one-time code,
lockout and replay protection, roles checked server-side, CSRF on every mutation, redaction for
anonymous and demo viewers, filter hot reload, manual codes, and the capped public demo."""

from __future__ import annotations

import json
from collections.abc import AsyncIterator
from uuid import uuid4

import httpx
import pyotp
import pytest
from sqlalchemy import text

from apikit import PASSWORD, Api, demo_client, items
from fw_core.db import tenant_tx
from fw_queue import keys

pytestmark = pytest.mark.integration


@pytest.fixture(scope="session")
async def owner(api: Api) -> AsyncIterator[httpx.AsyncClient]:
    c = await api.signed_in("owner")
    try:
        yield c
    finally:
        await c.aclose()


@pytest.fixture(scope="session")
async def operator(api: Api) -> AsyncIterator[httpx.AsyncClient]:
    c = await api.signed_in("operator")
    try:
        yield c
    finally:
        await c.aclose()


@pytest.fixture(scope="session")
async def viewer(api: Api) -> AsyncIterator[httpx.AsyncClient]:
    c = await api.signed_in("viewer")
    try:
        yield c
    finally:
        await c.aclose()


@pytest.fixture(scope="session")
async def demo(api: Api) -> AsyncIterator[httpx.AsyncClient]:
    c = await demo_client(api)
    try:
        yield c
    finally:
        await c.aclose()


async def test_sign_in_needs_password_then_code(api: Api, owner: httpx.AsyncClient) -> None:
    me = (await owner.get("/v1/session")).json()
    assert me["authenticated"] and me["role"] == "owner"
    assert me["tenant"]["id"] == str(api.tenant_id)
    assert me["email"] == api.users["owner"].email  # not redacted for staff
    # the code step without the password step's cookie is refused
    async with api.client() as c:
        r = await c.post("/v1/auth/mfa", json={"code": pyotp.TOTP(api.users["owner"].totp).now()})
        assert r.status_code == 401


async def test_unknown_user_and_wrong_password_get_the_same_answer(api: Api) -> None:
    async with api.client() as c:
        unknown = await c.post(
            "/v1/auth/login", json={"email": f"nobody-{uuid4().hex[:8]}@example.test", "password": PASSWORD}
        )
        wrong = await c.post("/v1/auth/login", json={"email": api.users["viewer"].email, "password": "nope"})
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()


async def test_a_code_cannot_be_used_twice(api: Api) -> None:
    user = api.users["replay"]
    code = pyotp.TOTP(user.totp).now()
    async with api.client() as first:
        await first.post("/v1/auth/login", json={"email": user.email, "password": PASSWORD})
        assert (await first.post("/v1/auth/mfa", json={"code": code})).status_code == 200
    async with api.client() as second:
        await second.post("/v1/auth/login", json={"email": user.email, "password": PASSWORD})
        assert (await second.post("/v1/auth/mfa", json={"code": code})).status_code == 401


async def test_repeated_failures_lock_the_account(api: Api) -> None:
    user = api.users["lockout"]
    limit = api.cfg.auth.login_max_attempts
    for _ in range(limit):
        async with api.client() as c:  # a new address each time: the email lock is what trips
            assert (await c.post("/v1/auth/login", json={"email": user.email, "password": "wrong"})).status_code == 401
    async with api.client() as c:
        r = await c.post("/v1/auth/login", json={"email": user.email, "password": PASSWORD})
    assert r.status_code == 429 and int(r.headers["Retry-After"]) > 0


async def test_anonymous_visitors_get_a_read_only_redacted_view(api: Api, owner: httpx.AsyncClient) -> None:
    async with api.client() as anon:
        me = (await anon.get("/v1/session")).json()
        assert me["role"] == "public" and not me["authenticated"] and me["redacted"]
        emails = [u["email"] for u in items(await anon.get("/v1/users"))]
        assert emails and all("•••" in e for e in emails)
        assert api.users["owner"].email not in json.dumps(emails)
        for entry in items(await anon.get("/v1/audit")):
            assert entry["ip"] == "hidden"
        r = await anon.post("/v1/filters", json={"name": "anon"}, headers={api.cfg.auth.csrf_header: "x"})
        assert r.status_code == 403
        r = await anon.post("/v1/demo/run", headers={api.cfg.auth.csrf_header: "x"})
        assert r.status_code == 403
    # staff see real addresses
    assert api.users["owner"].email in json.dumps(items(await owner.get("/v1/users")))


async def test_every_read_endpoint_answers_in_the_contract_shape(api: Api, viewer: httpx.AsyncClient) -> None:
    for path in ("/v1/workers", "/v1/accounts", "/v1/claims", "/v1/filters", "/v1/schedules", "/v1/audit", "/v1/users"):
        body = (await viewer.get(path)).json()
        assert set(body) == {"tenant_id", "items", "next_cursor", "total_estimate"}, path
        assert all(i["tenant_id"] == str(api.tenant_id) for i in body["items"]), path
    accounts = items(await viewer.get("/v1/accounts"))
    assert len(accounts) == 4 and {a["target"] for a in accounts} == {"demo-board"}
    assert {f["name"] for f in items(await viewer.get("/v1/filters"))} >= {"Everything over $900", "Texas outbound"}
    overview = (await viewer.get("/v1/overview")).json()
    assert {"claims", "series", "workers", "alerts"} <= set(overview)
    assert "stages" in (await viewer.get("/v1/latency")).json()
    cells = items(await viewer.get("/v1/cells"))
    assert [c for c in cells if c["hosts_you"]], "the tenant's own cell is marked"
    assert all("tenants" not in c for c in cells)  # other tenants are counted, never listed
    assert (await viewer.get("/v1/demo")).json()["caps"]


async def test_roles_are_enforced_server_side(
    api: Api, viewer: httpx.AsyncClient, operator: httpx.AsyncClient, demo: httpx.AsyncClient
) -> None:
    body = {"name": "Role check", "min_rate_usd": 1200}
    assert (await viewer.post("/v1/filters", json=body)).status_code == 403
    assert (await demo.post("/v1/filters", json=body)).status_code == 403
    created = await operator.post("/v1/filters", json=body)
    assert created.status_code == 201, created.text
    fid = created.json()["id"]
    assert (await viewer.patch(f"/v1/filters/{fid}", json={"enabled": False})).status_code == 403
    assert (await viewer.post("/v1/demo/run")).status_code == 403
    account = items(await operator.get("/v1/accounts"))[0]["id"]
    assert (await viewer.post(f"/v1/accounts/{account}/otp", json={"code": "123456"})).status_code == 403


async def test_mutations_need_the_csrf_token(api: Api, operator: httpx.AsyncClient) -> None:
    header = api.cfg.auth.csrf_header
    token = operator.headers.pop(header)
    try:
        assert (await operator.post("/v1/filters", json={"name": "No token"})).status_code == 403
        r = await operator.post("/v1/filters", json={"name": "Bad token"}, headers={header: "forged"})
        assert r.status_code == 403
    finally:
        operator.headers[header] = token


async def test_filter_changes_are_audited_and_reload_dispatchers(api: Api, operator: httpx.AsyncClient) -> None:
    redis = api.app.state.services.redis
    pubsub = redis.pubsub()
    await pubsub.subscribe(keys.filters_channel(api.tenant_id))
    try:
        await pubsub.get_message(timeout=1.0)  # subscribe confirmation
        created = await operator.post("/v1/filters", json={"name": "Reload check", "min_rate_usd": 700})
        assert created.status_code == 201
        message = None
        for _ in range(20):
            message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=0.5)
            if message:
                break
        assert message is not None, "dispatchers were not told to reload"
        fid = created.json()["id"]
        patched = await operator.patch(f"/v1/filters/{fid}", json={"enabled": False, "min_rate_usd": 750})
        assert patched.status_code == 200
        assert patched.json()["enabled"] is False and patched.json()["version"] == 2
        assert (await operator.patch(f"/v1/filters/{fid}", json={"name": "Texas outbound"})).status_code == 409
    finally:
        await pubsub.aclose()
    actions = [e["action"] for e in items(await operator.get("/v1/audit"))]
    assert "filter.create" in actions and "filter.update" in actions


async def test_a_manual_code_reaches_the_waiting_worker_but_not_the_audit_log(
    api: Api, operator: httpx.AsyncClient
) -> None:
    account = items(await operator.get("/v1/accounts"))[0]["id"]
    r = await operator.post(f"/v1/accounts/{account}/otp", json={"code": "481516"})
    assert r.status_code == 202
    redis = api.app.state.services.redis
    assert await redis.lpop(keys.manual_otp(api.tenant_id, account)) in (b"481516", "481516")
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        details = (
            (await conn.execute(text("SELECT detail FROM audit_log WHERE tenant_id = :t"), {"t": api.tenant_id}))
            .scalars()
            .all()
        )
    assert not any("481516" in d for d in details)


async def test_the_demo_is_capped_and_resets_itself(api: Api, demo: httpx.AsyncClient) -> None:
    me = (await demo.get("/v1/session")).json()
    assert me["role"] == "demo" and me["redacted"] and me["demo"]["can_control"]
    caps = (await demo.get("/v1/demo")).json()["caps"]
    too_much = caps["ack_loss_rate"]["max"] + 0.1
    r = await demo.patch("/v1/demo/adversity", json={"changes": {"ack_loss_rate": too_much}})
    assert r.status_code == 422
    assert (await demo.patch("/v1/demo/adversity", json={"changes": {"rate_limit_per_min": 1}})).status_code == 422
    r = await demo.patch("/v1/demo/adversity", json={"changes": {"ack_loss_rate": 0.1, "layout_variant": "b"}})
    assert r.status_code == 200, r.text
    assert r.json()["adversity"]["ack_loss_rate"] == 0.1
    run = await demo.post("/v1/demo/run")
    assert run.status_code == 200
    assert run.json()["run_active"] and run.json()["feed_rate_per_min"] <= api.cfg.demo.run_max_rate_per_min
    # a second press neither stacks nor extends the run
    assert (await demo.post("/v1/demo/run")).status_code == 409
    # time passes: the run and the change window end, and the reset loop restores the idle preset
    svc = api.app.state.services
    await svc.redis.delete(keys.demo_run(), keys.demo_changed())
    assert set(await svc.demo.reset_due()) == {"run", "adversity"}
    status = await svc.demo.status()
    idle = svc.demo.data.idle
    assert status["feed_rate_per_min"] == idle["feed_rate_per_min"]
    assert status["adversity"]["ack_loss_rate"] == idle["ack_loss_rate"]
    assert status["adversity"]["layout_variant"] == idle["layout_variant"]


async def test_sign_out_ends_the_session(api: Api) -> None:
    c = await api.signed_in("signout")  # its own user: one code per user per time step
    try:
        assert (await c.post("/v1/auth/logout")).status_code == 200
        me = (await c.get("/v1/session")).json()
        assert me["role"] == "public"
    finally:
        await c.aclose()


async def test_claims_and_workers_come_back_in_the_contract_shape(api: Api, viewer: httpx.AsyncClient) -> None:
    """Real rows (not just empty lists) pass the strict response models, including NULL times."""
    engine = api.app.state.services.engine
    claim_id, worker_id = uuid4(), f"w-{uuid4().hex[:8]}"
    async with tenant_tx(engine, api.tenant_id) as conn:
        await conn.execute(
            text(
                """INSERT INTO claims (tenant_id, id, target_job_key, state, cell_id, lane, rate_usd, seen_at,
                                       worker_id, fence, leased_at)
                   VALUES (:t, :c, :k, 'LEASED', 'cell-a', 'Dallas, TX -> Denver, CO', 1450, clock_timestamp(),
                           :w, 7, clock_timestamp())"""
            ),
            {"t": api.tenant_id, "c": claim_id, "k": f"job-{claim_id.hex[:8]}", "w": worker_id},
        )
        await conn.execute(
            text(
                "INSERT INTO claim_events (tenant_id, claim_id, state, actor, note) VALUES (:t, :c, 'QUEUED', 'dispatcher', NULL)"
            ),
            {"t": api.tenant_id, "c": claim_id},
        )
        await conn.execute(
            text(
                """INSERT INTO workers (tenant_id, id, process_id, cell_id, mode, version, memory_mb, cpu_pct)
                   VALUES (:t, :w, 'p-test', 'cell-a', 'claimer', 'test', 310, 12.5)"""
            ),
            {"t": api.tenant_id, "w": worker_id},
        )
    listed = items(await viewer.get("/v1/claims"))
    mine = next(c for c in listed if c["id"] == str(claim_id))
    assert mine["published_at"] is None and mine["fencing_token"] == 7
    detail = (await viewer.get(f"/v1/claims/{claim_id}")).json()
    assert [e["state"] for e in detail["events"]] == ["QUEUED"]
    assert (await viewer.get(f"/v1/claims/{uuid4()}")).status_code == 404
    worker = next(w for w in items(await viewer.get("/v1/workers")) if w["id"] == worker_id)
    assert worker["status"] == "healthy" and worker["mode"] == "claimer"
    cell = next(c for c in items(await viewer.get("/v1/cells")) if c["id"] == "cell-a")
    assert cell["your_workers"] >= 1
    overview = (await viewer.get("/v1/overview")).json()
    assert overview["claims"]["by_state"].get("LEASED", 0) >= 1 and overview["workers"]["total"] >= 1
    assert overview["claims"]["total"] >= 1 and overview["claims"]["window_s"] == api.cfg.api.series_minutes * 60
