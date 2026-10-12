"""Acceptance tests for general durable execution, approvals, isolation and evidence."""

from __future__ import annotations

import asyncio
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apikit import Api
from fw_core import workflows as jobs
from fw_core.db import tenant_tx
from fw_core.settings import WorkflowSettings
from fw_core.workflow_contracts import digest, load_workflows

pytestmark = pytest.mark.integration


async def proposal(api: Api, workflow: str = "service-request") -> tuple[jobs.Access, dict, UUID, str]:
    engine = api.app.state.services.engine
    async with tenant_tx(engine, api.tenant_id) as conn:
        user = await conn.scalar(text("SELECT id FROM users WHERE tenant_id=:t AND role='owner'"), {"t": api.tenant_id})
        account = await conn.scalar(text("SELECT id FROM accounts WHERE tenant_id=:t LIMIT 1"), {"t": api.tenant_id})
        _grant, token = await jobs.issue_access(conn, api.tenant_id, user, frozenset({"observe", "execute"}), 3600)
        access = await jobs.authorize(conn, api.tenant_id, token, "execute")
        spec = load_workflows(api.cfg.config_dir).get(workflow)
        inputs = {"reference": "test-" + uuid4().hex}
        if workflow == "service-request":
            inputs.update(title="Repair demonstration", priority="normal")
        result = await jobs.submit(conn, access, uuid4().hex, workflow, spec, account, inputs)
    return access, result, user, token


async def approved(api: Api) -> tuple[jobs.Access, dict, UUID, str]:
    access, job, user, token = await proposal(api)
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        await jobs.approve(conn, api.tenant_id, UUID(job["id"]), job["action_hash"], user, 300)
    return access, job, user, token


async def test_idempotency_binds_full_action(api: Api) -> None:
    access, job, _user, _token = await proposal(api)
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        row = (
            (
                await conn.execute(
                    text("SELECT * FROM workflow_jobs WHERE tenant_id=:t AND id=:j"),
                    {"t": api.tenant_id, "j": UUID(job["id"])},
                )
            )
            .mappings()
            .one()
        )
        spec = load_workflows(api.cfg.config_dir).get(row["workflow"])
        again = await jobs.submit(
            conn, access, job["identity"], row["workflow"], spec, row["account_id"], row["inputs"]
        )
        assert again["id"] == job["id"]
        with pytest.raises(jobs.Conflict):
            await jobs.submit(
                conn,
                access,
                job["identity"],
                row["workflow"],
                spec,
                row["account_id"],
                {**row["inputs"], "priority": "urgent"},
            )


async def test_competing_workers_have_one_winner_and_stale_fence_fails(api: Api) -> None:
    _access, job, _user, _token = await approved(api)
    engine, tenant, key = api.app.state.services.engine, api.tenant_id, UUID(job["id"])

    async def compete(n: int) -> jobs.Held | None:
        async with tenant_tx(engine, tenant) as conn:
            return await jobs.take(conn, tenant, key, f"worker-{n}", 90)

    winners = [held for held in await asyncio.gather(*(compete(n) for n in range(20))) if held]
    assert len(winners) == 1
    held = winners[0]
    async with tenant_tx(engine, tenant) as conn:
        spec = load_workflows(api.cfg.config_dir).get("service-request")
        assert not await jobs.begin_action(
            conn, jobs.Held(tenant, key, held.fence - 1, held.worker), spec, WorkflowSettings()
        )
        assert await jobs.begin_action(conn, held, spec, WorkflowSettings())
        assert not await jobs.begin_action(conn, held, spec, WorkflowSettings())
        assert await jobs.finish(conn, held, "CONFIRMED", {"verified": True})


async def test_crash_after_acting_never_blindly_retries(api: Api) -> None:
    _access, job, _user, _token = await approved(api)
    engine, tenant, key = api.app.state.services.engine, api.tenant_id, UUID(job["id"])
    async with tenant_tx(engine, tenant) as conn:
        held = await jobs.take(conn, tenant, key, "dead-worker", 90)
        assert held
        assert await jobs.begin_action(
            conn, held, load_workflows(api.cfg.config_dir).get("service-request"), WorkflowSettings()
        )
        await conn.execute(
            text(
                "UPDATE workflow_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id=:t AND id=:j"
            ),
            {"t": tenant, "j": key},
        )
    async with tenant_tx(engine, tenant) as conn:
        assert await jobs.recover(conn, tenant, 100) >= 1
        assert (await jobs.inspect(conn, tenant, key))["state"] == "UNKNOWN"
        assert await jobs.take(conn, tenant, key, "replacement", 90) is None
        assert not await jobs.finish(conn, held, "CONFIRMED", {})
        assert not await jobs.reconcile(conn, tenant, key, job["action_hash"], None, "")
        assert (await jobs.inspect(conn, tenant, key))["state"] == "UNKNOWN"
        assert await jobs.reconcile(conn, tenant, key, job["action_hash"], "CONFIRMED", digest({"receipt": "test"}))


@pytest.mark.parametrize("change", ["inputs", "contract", "expired", "revoked", "grant", "role"])
async def test_changed_or_expired_approval_cannot_authorize_action(api: Api, change: str) -> None:
    access, job, user, _token = await approved(api)
    engine, tenant, key = api.app.state.services.engine, api.tenant_id, UUID(job["id"])
    async with tenant_tx(engine, tenant) as conn:
        held = await jobs.take(conn, tenant, key, "test-worker", 90)
        # A prior parameter can leave a leased account. Expire those independently in this test.
        if held is None:
            await conn.execute(
                text("UPDATE accounts SET holder_expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id=:t"),
                {"t": tenant},
            )
            await conn.execute(
                text(
                    "UPDATE workflow_jobs SET lease_expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id=:t AND state='LEASED'"
                ),
                {"t": tenant},
            )
            await jobs.recover(conn, tenant, 1000)
            held = await jobs.take(conn, tenant, key, "test-worker", 90)
        assert held
        spec = load_workflows(api.cfg.config_dir).get("service-request")
        if change == "inputs":
            await conn.execute(
                text(
                    "UPDATE workflow_jobs SET inputs=jsonb_set(inputs,'{priority}','\"urgent\"') WHERE tenant_id=:t AND id=:j"
                ),
                {"t": tenant, "j": key},
            )
        elif change == "contract":
            spec = spec.model_copy(update={"revision": 2})
        elif change == "expired":
            await conn.execute(
                text(
                    "UPDATE workflow_approvals SET expires_at=clock_timestamp()-interval '1 second' WHERE tenant_id=:t AND job_id=:j"
                ),
                {"t": tenant, "j": key},
            )
        elif change == "revoked":
            await jobs.revoke_approval(conn, tenant, key)
        elif change == "grant":
            await jobs.revoke_access(conn, tenant, access.grant, user)
        else:
            await conn.execute(
                text("UPDATE users SET role='viewer' WHERE tenant_id=:t AND id=:u"), {"t": tenant, "u": user}
            )
        assert not await jobs.begin_action(conn, held, spec, WorkflowSettings())
        await jobs.cancel(conn, tenant, key)
        if change == "role":
            await conn.execute(
                text("UPDATE users SET role='owner' WHERE tenant_id=:t AND id=:u"), {"t": tenant, "u": user}
            )


async def test_cross_tenant_lookup_and_revocation_denied(api: Api) -> None:
    access, job, user, token = await proposal(api)
    engine = api.app.state.services.engine
    async with tenant_tx(engine, uuid4()) as conn:
        with pytest.raises(jobs.Denied):
            await jobs.inspect(conn, uuid4(), UUID(job["id"]))
        with pytest.raises(jobs.Denied):
            await jobs.authorize(conn, uuid4(), token, "observe")
    async with tenant_tx(engine, api.tenant_id) as conn:
        await jobs.revoke_access(conn, api.tenant_id, access.grant, user)
        with pytest.raises(jobs.Denied):
            await jobs.authorize(conn, api.tenant_id, token, "observe")


async def test_observation_scope_cannot_submit_or_cancel(api: Api) -> None:
    _access, _job, user, _token = await proposal(api)
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        _grant, token = await jobs.issue_access(conn, api.tenant_id, user, frozenset({"observe"}), 3600)
        await jobs.authorize(conn, api.tenant_id, token, "observe")
        with pytest.raises(jobs.Denied):
            await jobs.authorize(conn, api.tenant_id, token, "execute")


async def test_cancel_after_acting_preserves_uncertainty(api: Api) -> None:
    _access, job, _user, _token = await approved(api)
    tenant, engine, key = api.tenant_id, api.app.state.services.engine, UUID(job["id"])
    async with tenant_tx(engine, tenant) as conn:
        held = await jobs.take(conn, tenant, key, "cancel-worker", 90)
        assert held and await jobs.begin_action(
            conn, held, load_workflows(api.cfg.config_dir).get("service-request"), WorkflowSettings()
        )
        cancelled = await jobs.cancel(conn, tenant, key)
        assert cancelled["state"] == "ACTING" and cancelled["cancel_requested"]
        await jobs.finish(conn, held, "UNKNOWN", {})


async def test_evidence_is_bounded_redacted_and_hash_verifiable(api: Api) -> None:
    _access, job, _user, _token = await proposal(api)
    tenant, engine, key = api.tenant_id, api.app.state.services.engine, UUID(job["id"])
    async with tenant_tx(engine, tenant) as conn:
        await jobs.event(conn, tenant, key, "test", {"cookie": "test-key", "password": "test-key", "state": "PENDING"})
        result = await jobs.evidence_page(conn, tenant, key, 0, WorkflowSettings(evidence_page_size=1))
        assert len(result["events"]) == 1 and result["next_cursor"] is not None
        assert digest({k: v for k, v in result.items() if k not in {"sha256", "integrity"}}) == result["sha256"]
        second = await jobs.evidence_page(conn, tenant, key, result["next_cursor"], WorkflowSettings())
        assert "test-key" not in str(second) and "inputs" not in second["job"]


async def test_audit_and_state_rollback_together(api: Api) -> None:
    _access, job, user, _token = await proposal(api)
    engine, tenant, key = api.app.state.services.engine, api.tenant_id, UUID(job["id"])
    with pytest.raises(RuntimeError):
        async with tenant_tx(engine, tenant) as conn:
            await jobs.approve(conn, tenant, key, job["action_hash"], user, 300)
            raise RuntimeError("simulate crash before commit")
    async with tenant_tx(engine, tenant) as conn:
        assert (await jobs.inspect(conn, tenant, key))["state"] == "PENDING"
        assert (
            await conn.scalar(
                text("SELECT count(*) FROM workflow_events WHERE tenant_id=:t AND job_id=:j AND kind='approved'"),
                {"t": tenant, "j": key},
            )
            == 0
        )
