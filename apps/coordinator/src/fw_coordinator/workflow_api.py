"""Human owner approval and grant management on the existing authenticated console API."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from fw_core import workflows as jobs
from fw_core.db import tenant_tx
from fw_core.workflow_contracts import load_workflows
from fw_core.workflow_health import prometheus, snapshot
from fw_queue.sessions import Principal, Role


class GrantIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scopes: frozenset[str]


class ApprovalIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    action_hash: str = Field(pattern="^[a-f0-9]{64}$")


def needs(who: Principal, role: Role) -> None:
    if who.role == "public" or not who.at_least(role):
        raise HTTPException(403, "not allowed for this role")


def install(
    app: FastAPI, services: Callable[..., Any], principal: Callable[..., Any], csrf_checked: Callable[..., Any]
) -> None:
    Svc = Annotated[Any, Depends(services)]
    Who = Annotated[Principal, Depends(principal)]
    Mutator = Annotated[Principal, Depends(csrf_checked)]

    @app.get("/v1/workflows/health")
    async def health(svc: Svc, who: Who) -> dict[str, Any]:
        needs(who, "operator")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await snapshot(
                conn, who.tenant_id, svc.cfg.workflows, load_workflows(svc.cfg.config_dir).operator_messages
            )

    @app.get("/v1/workflows/metrics", response_class=PlainTextResponse)
    async def metrics(request: Request, svc: Svc) -> PlainTextResponse:
        # Scrapers use the same revocable observation grant as MCP, rather than an MFA cookie.
        authorization = request.headers.get("Authorization", "")
        try:
            tenant = UUID(request.headers.get("X-Fleetwright-Tenant", ""))
        except ValueError as exc:
            raise HTTPException(403, "observation grant required") from exc
        if not authorization.startswith("Bearer "):
            raise HTTPException(403, "observation grant required")
        async with tenant_tx(svc.engine, tenant) as conn:
            await jobs.authorize(conn, tenant, authorization.removeprefix("Bearer "), "observe")
            result = await snapshot(
                conn, tenant, svc.cfg.workflows, load_workflows(svc.cfg.config_dir).operator_messages
            )
        return PlainTextResponse(prometheus(result), media_type="text/plain; version=0.0.4")

    @app.exception_handler(jobs.Denied)
    async def denied(_: Request, __: jobs.Denied) -> Any:
        return JSONResponse({"detail": "access denied or job unavailable"}, status_code=403)

    @app.exception_handler(jobs.Conflict)
    async def conflict(_: Request, __: jobs.Conflict) -> Any:
        return JSONResponse({"detail": "action changed or approval no longer valid"}, status_code=409)

    @app.post("/v1/workflow-grants", status_code=201)
    async def issue(body: GrantIn, svc: Svc, who: Mutator) -> dict[str, Any]:
        needs(who, "owner")
        if who.user_id is None or not body.scopes or not body.scopes <= jobs.SCOPES:
            raise HTTPException(422, "invalid grant scopes")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            grant, token = await jobs.issue_access(
                conn, who.tenant_id, who.user_id, body.scopes, svc.cfg.workflows.grant_ttl_s
            )
        return {
            "grant_id": str(grant),
            "tenant_id": str(who.tenant_id),
            "access_token": token,
            "expires_in_s": svc.cfg.workflows.grant_ttl_s,
        }

    @app.delete("/v1/workflow-grants/{grant_id}")
    async def revoke(grant_id: UUID, svc: Svc, who: Mutator) -> dict[str, bool]:
        needs(who, "owner")
        if who.user_id is None:
            raise HTTPException(403, "human owner required")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            await jobs.revoke_access(conn, who.tenant_id, grant_id, who.user_id)
        return {"revoked": True}

    @app.get("/v1/workflows/jobs/{job_id}")
    async def proposal(job_id: UUID, svc: Svc, who: Who) -> dict[str, Any]:
        needs(who, "operator")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            info = await jobs.inspect(conn, who.tenant_id, job_id)
            # Human review requires exact inputs; MCP investigation/export intentionally excludes them.
            row = (
                await conn.execute(
                    text("SELECT inputs FROM workflow_jobs WHERE tenant_id=:t AND id=:j"),
                    {"t": who.tenant_id, "j": job_id},
                )
            ).one()
            return {**info, "inputs": row.inputs}

    @app.get("/v1/workflows/jobs")
    async def listing(svc: Svc, who: Who, cursor: UUID | None = None) -> dict[str, Any]:
        needs(who, "operator")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await jobs.list_page(conn, who.tenant_id, svc.cfg.workflows.evidence_page_size, cursor)

    @app.post("/v1/workflows/jobs/{job_id}/approve")
    async def approve(job_id: UUID, body: ApprovalIn, svc: Svc, who: Mutator) -> dict[str, bool]:
        needs(who, "owner")
        if who.user_id is None:
            raise HTTPException(403, "human owner required")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            await jobs.approve(
                conn, who.tenant_id, job_id, body.action_hash, who.user_id, svc.cfg.workflows.approval_ttl_s
            )
        return {"approved": True}

    @app.post("/v1/workflows/jobs/{job_id}/cancel")
    async def cancel(job_id: UUID, svc: Svc, who: Mutator) -> dict[str, Any]:
        needs(who, "operator")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await jobs.cancel(conn, who.tenant_id, job_id)

    @app.delete("/v1/workflows/jobs/{job_id}/approval")
    async def revoke_approval(job_id: UUID, svc: Svc, who: Mutator) -> dict[str, bool]:
        needs(who, "owner")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            await jobs.inspect(conn, who.tenant_id, job_id)
            await jobs.revoke_approval(conn, who.tenant_id, job_id)
        return {"revoked": True}

    @app.get("/v1/workflows/jobs/{job_id}/evidence")
    async def evidence(job_id: UUID, svc: Svc, who: Who, cursor: int = 0) -> dict[str, Any]:
        needs(who, "operator")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            return await jobs.evidence_page(conn, who.tenant_id, job_id, cursor, svc.cfg.workflows)
