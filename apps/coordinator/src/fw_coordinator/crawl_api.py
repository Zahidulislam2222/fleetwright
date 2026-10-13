"""Authenticated crawl submission, inspection, cancellation and private artifact export."""

from collections.abc import Callable
from typing import Annotated, Any
from uuid import UUID

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from fw_coordinator.crawl_contracts import definitions
from fw_coordinator.crawls import submit
from fw_core.db import tenant_tx
from fw_queue.sessions import Principal


class SubmitIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    definition: str = Field(pattern="^[a-z][a-z0-9-]{0,63}$")


def install(
    app: FastAPI,
    services: Callable[..., Any],
    principal: Callable[..., Any],
    csrf_checked: Callable[..., Any],
    audit: Callable[..., Any],
) -> None:
    Svc = Annotated[Any, Depends(services)]
    Who = Annotated[Principal, Depends(principal)]
    Mutator = Annotated[Principal, Depends(csrf_checked)]

    @app.get("/v1/crawls/contracts")
    async def contracts(svc: Svc, who: Who) -> dict[str, Any]:
        return {
            name: {
                "name": definition.name,
                "personal_data": definition.personal_data,
                "respect_robots": definition.respect_robots,
            }
            for name, definition in definitions(svc.cfg.config_dir).definitions.items()
        }

    @app.get("/v1/crawls/jobs")
    async def listing(svc: Svc, who: Who, cursor: UUID | None = None, limit: int | None = None) -> dict[str, Any]:
        size = min(max(limit if limit is not None else svc.cfg.api.page_size_default, 1), svc.cfg.api.page_size_max)
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            rows = (
                (
                    await conn.execute(
                        text(
                            "SELECT id,definition,state,created_at,completed_at,pages,items,errors,added,changed,removed,alerts, "
                            "artifact IS NOT NULL AS export_available "
                            "FROM crawl_jobs WHERE tenant_id=:t AND (CAST(:cursor AS uuid) IS NULL OR id<CAST(:cursor AS uuid)) "
                            "ORDER BY id DESC LIMIT :limit"
                        ),
                        {"t": who.tenant_id, "cursor": cursor, "limit": size + 1},
                    )
                )
                .mappings()
                .all()
            )
        return {
            "items": [dict(row) for row in rows[:size]],
            "next_cursor": str(rows[size - 1]["id"]) if len(rows) > size else None,
        }

    @app.post("/v1/crawls/jobs", status_code=201)
    async def create(body: SubmitIn, request: Request, svc: Svc, who: Mutator) -> dict[str, str]:
        if not who.at_least("operator") or who.user_id is None:
            raise HTTPException(403, "operator required")
        contract = definitions(svc.cfg.config_dir).definitions.get(body.definition)
        if contract is None:
            raise HTTPException(422, "unknown crawl definition")
        if len(set(contract.seeds)) > svc.cfg.crawl.max_pages:
            raise HTTPException(422, "crawl seeds exceed the configured page budget")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            try:
                job = await submit(conn, who.tenant_id, body.definition, contract, svc.cfg.crawl.max_pages)
            except ValueError as exc:
                raise HTTPException(409, "crawl already active") from exc
            await audit(svc, who, request, "crawl.create", str(job), body.definition, conn)
        return {"id": str(job), "state": "QUEUED"}

    @app.post("/v1/crawls/jobs/{job_id}/cancel")
    async def cancel(job_id: UUID, request: Request, svc: Svc, who: Mutator) -> dict[str, bool]:
        if not who.at_least("operator") or who.user_id is None:
            raise HTTPException(403, "operator required")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            result = await conn.execute(
                text(
                    "UPDATE crawl_jobs SET cancel_requested=true WHERE tenant_id=:t AND id=:j "
                    "AND state IN ('QUEUED','RUNNING')"
                ),
                {"t": who.tenant_id, "j": job_id},
            )
            if not result.rowcount:
                raise HTTPException(404, "active crawl unavailable")
            await audit(svc, who, request, "crawl.cancel", str(job_id), "requested", conn)
        return {"cancel_requested": True}

    @app.get("/v1/crawls/jobs/{job_id}/export")
    async def export(job_id: UUID, svc: Svc, who: Who) -> FileResponse:
        if not who.at_least("operator") or who.user_id is None:
            raise HTTPException(403, "operator required")
        async with tenant_tx(svc.engine, who.tenant_id) as conn:
            exists = await conn.scalar(
                text("SELECT artifact FROM crawl_jobs WHERE tenant_id=:t AND id=:j AND state IN ('COMPLETE','FAILED')"),
                {"t": who.tenant_id, "j": job_id},
            )
        path = svc.cfg.crawl.output_directory / str(who.tenant_id) / (str(job_id) + ".jsonl")
        if not exists or not path.is_file() or path.is_symlink():
            raise HTTPException(404, "crawl export unavailable or expired")
        return FileResponse(
            path,
            filename=str(job_id) + ".jsonl",
            media_type="application/x-ndjson",
            headers={"Cache-Control": "no-store"},
        )
