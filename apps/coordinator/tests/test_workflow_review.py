"""Regressions from independent review, including actual HTTP authorization boundaries."""

from contextlib import aclosing
from uuid import UUID

import pytest
from sqlalchemy import text
from test_workflows import approved, proposal

from apikit import Api
from fw_core import workflows as jobs
from fw_core.db import tenant_tx
from fw_core.settings import WorkflowSettings
from fw_core.workflow_contracts import load_workflows

pytestmark = pytest.mark.integration


async def test_reconciliation_rotates_past_inconclusive_jobs(api: Api) -> None:
    _, first, _, _ = await approved(api)
    _, second, _, _ = await approved(api)
    tenant, engine = api.tenant_id, api.app.state.services.engine
    async with tenant_tx(engine, tenant) as conn:
        for job in (first, second):
            held = await jobs.take(conn, tenant, UUID(job["id"]), "review-rotation", 90)
            assert held and await jobs.begin_action(
                conn, held, load_workflows(api.cfg.config_dir).get("service-request"), WorkflowSettings()
            )
            assert await jobs.finish(conn, held, "UNKNOWN", {})
        cfg = WorkflowSettings(evidence_page_size=1, reconcile_grace_s=0)
        seen = set()
        for _ in range(1000):
            batch = await jobs.reconciliation_batch(conn, tenant, cfg)
            if not batch:
                break
            seen.add(str(batch[0]["id"]))
        assert first["id"] in seen and second["id"] in seen
        assert (await jobs.inspect(conn, tenant, UUID(first["id"])))["state"] == "UNKNOWN"


async def test_acting_refreshes_job_and_account_lease(api: Api) -> None:
    _, job, _, _ = await approved(api)
    tenant, key = api.tenant_id, UUID(job["id"])
    async with tenant_tx(api.app.state.services.engine, tenant) as conn:
        held = await jobs.take(conn, tenant, key, "review-lease", 90)
        assert held
        await conn.execute(
            text("""UPDATE workflow_jobs SET lease_expires_at=clock_timestamp()+interval '1 second'
                                WHERE tenant_id=:t AND id=:j"""),
            {"t": tenant, "j": key},
        )
        assert await jobs.begin_action(
            conn, held, load_workflows(api.cfg.config_dir).get("service-request"), WorkflowSettings()
        )
        seconds = await conn.scalar(
            text("""SELECT extract(epoch FROM least(j.lease_expires_at,a.holder_expires_at)-clock_timestamp())
                FROM workflow_jobs j JOIN accounts a ON (a.tenant_id,a.id)=(j.tenant_id,j.account_id)
                WHERE j.tenant_id=:t AND j.id=:j"""),
            {"t": tenant, "j": key},
        )
        assert seconds > 80
        assert await jobs.finish(conn, held, "CONFIRMED", {"verified": True})


async def test_invalid_approval_cannot_starve_ready_work(api: Api) -> None:
    _, older, _, _ = await approved(api)
    _, newer, _, _ = await approved(api)
    tenant = api.tenant_id
    async with tenant_tx(api.app.state.services.engine, tenant) as conn:
        await jobs.revoke_approval(conn, tenant, UUID(older["id"]))
        ready = await jobs.ready_jobs(conn, tenant, 1000)
        assert UUID(older["id"]) not in ready and UUID(newer["id"]) in ready
        held = await jobs.take(conn, tenant, UUID(newer["id"]), "review-reject", 90)
        assert held
        await jobs.revoke_approval(conn, tenant, UUID(newer["id"]))
        assert not await jobs.begin_action(
            conn, held, load_workflows(api.cfg.config_dir).get("service-request"), WorkflowSettings()
        )
        await jobs.reject_before_action(conn, held)
        assert (await jobs.inspect(conn, tenant, UUID(newer["id"])))["state"] == "PENDING"
        await jobs.cancel(conn, tenant, UUID(older["id"]))
        await jobs.cancel(conn, tenant, UUID(newer["id"]))


async def test_disabled_account_rejected_at_submit_and_before_acting(api: Api) -> None:
    access, job, _, _ = await approved(api)
    tenant, key = api.tenant_id, UUID(job["id"])
    async with tenant_tx(api.app.state.services.engine, tenant) as conn:
        held = await jobs.take(conn, tenant, key, "review-disabled", 90)
        assert held
        account = await conn.scalar(
            text("SELECT account_id FROM workflow_jobs WHERE tenant_id=:t AND id=:j"), {"t": tenant, "j": key}
        )
        await conn.execute(
            text("UPDATE accounts SET enabled=false WHERE tenant_id=:t AND id=:a"), {"t": tenant, "a": account}
        )
        spec = load_workflows(api.cfg.config_dir).get("service-request")
        with pytest.raises(jobs.Denied):
            await jobs.submit(
                conn,
                access,
                "disabled-test",
                "service-request",
                spec,
                account,
                {"reference": "disabled-test", "title": "Test", "priority": "normal"},
            )
        assert not await jobs.begin_action(conn, held, spec, WorkflowSettings())
        await jobs.cancel(conn, tenant, key)
        await conn.execute(
            text("UPDATE accounts SET enabled=true WHERE tenant_id=:t AND id=:a"), {"t": tenant, "a": account}
        )


async def test_http_owner_approval_csrf_and_revocable_metrics(api: Api) -> None:
    _, job, _, _token = await proposal(api)
    path = f"/v1/workflows/jobs/{job['id']}"
    async with aclosing(await api.signed_in("operator")) as operator:
        assert (await operator.get(path)).json()["inputs"]["priority"] == "normal"
        assert (await operator.post(path + "/approve", json={"action_hash": job["action_hash"]})).status_code == 403
    async with aclosing(await api.signed_in("owner")) as owner:
        csrf = owner.headers.pop(api.cfg.auth.csrf_header)
        assert (await owner.post(path + "/approve", json={"action_hash": job["action_hash"]})).status_code == 403
        owner.headers[api.cfg.auth.csrf_header] = csrf
        assert (await owner.post(path + "/approve", json={"action_hash": "0" * 64})).status_code == 409
        assert (await owner.post(path + "/approve", json={"action_hash": job["action_hash"]})).status_code == 200
        assert (await owner.post(path + "/approve", json={"action_hash": job["action_hash"]})).status_code == 409
        grant = (await owner.post("/v1/workflow-grants", json={"scopes": ["observe"]})).json()
        headers = {"Authorization": "Bearer " + grant["access_token"], "X-Fleetwright-Tenant": grant["tenant_id"]}
        assert (await owner.get("/v1/workflows/metrics")).status_code == 403
        metrics = await owner.get("/v1/workflows/metrics", headers=headers)
        assert metrics.status_code == 200 and "fleetwright_workflow_jobs" in metrics.text
        assert (await owner.delete("/v1/workflow-grants/" + grant["grant_id"])).status_code == 200
        assert (await owner.get("/v1/workflows/metrics", headers=headers)).status_code == 403
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        await jobs.cancel(conn, api.tenant_id, UUID(job["id"]))
