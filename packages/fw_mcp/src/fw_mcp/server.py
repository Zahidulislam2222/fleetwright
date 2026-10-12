"""Local stdio MCP server. Each invocation reloads authorization from Postgres.

The configured tenant and bearer grant define this server's boundary. Approval is intentionally
absent: only the authenticated human owner API can approve exact proposed actions.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any
from uuid import UUID

from mcp.server.fastmcp import FastMCP

from fw_core import workflows as jobs
from fw_core.db import make_engine, tenant_tx
from fw_core.settings import McpAppSettings, load
from fw_core.workflow_contracts import load_workflows


def create_server(cfg: McpAppSettings) -> FastMCP:
    engine = make_engine(cfg.app_db.dsn, cfg.app_db, "fw-mcp")
    tenant = UUID(cfg.mcp.tenant_id)
    contracts = load_workflows(cfg.config_dir)

    @asynccontextmanager
    async def lifespan(_: FastMCP) -> AsyncIterator[dict[str, Any]]:
        try:
            yield {}
        finally:
            await engine.dispose()

    server = FastMCP(contracts.server_name, instructions=contracts.instructions, lifespan=lifespan)

    async def call(scope: jobs.Scope, operation: str, arguments: dict[str, Any]) -> dict[str, Any]:
        async with tenant_tx(engine, tenant) as conn:
            access = await jobs.authorize(conn, tenant, cfg.mcp.access_token.get_secret_value(), scope)
            if operation == "contracts":
                return {
                    "workflows": {
                        k: {
                            "description": s.description,
                            "revision": s.revision,
                            "contract_hash": s.fingerprint,
                            "fields": {name: field.model_dump(mode="json") for name, field in s.fields.items()},
                        }
                        for k, s in contracts.workflows.items()
                    }
                }
            if operation == "submit":
                return await jobs.submit(
                    conn,
                    access,
                    arguments["identity"],
                    arguments["workflow"],
                    contracts.get(arguments["workflow"]),
                    arguments["account_id"],
                    arguments["inputs"],
                )
            if operation == "list":
                return await jobs.list_page(conn, tenant, cfg.workflows.evidence_page_size, arguments["cursor"])
            if operation == "inspect":
                return await jobs.inspect(conn, tenant, arguments["job_id"])
            if operation == "cancel":
                return await jobs.cancel(conn, tenant, arguments["job_id"])
            return await jobs.evidence_page(conn, tenant, arguments["job_id"], arguments["cursor"], cfg.workflows)

    @server.tool()
    async def workflow_contracts() -> dict[str, Any]:
        """List supported owned workflows and their required input fields."""
        return await call("observe", "contracts", {})

    @server.tool()
    async def submit_workflow(identity: str, workflow: str, account_id: UUID, inputs: dict[str, str]) -> dict[str, Any]:
        """Persist an idempotent proposal. Execution waits for exact-action human owner approval."""
        return await call(
            "execute",
            "submit",
            {"identity": identity, "workflow": workflow, "account_id": account_id, "inputs": inputs},
        )

    @server.tool()
    async def list_jobs(cursor: UUID | None = None) -> dict[str, Any]:
        """Inspect a bounded job page for this tenant; pass next_cursor to see older work."""
        return await call("observe", "list", {"cursor": cursor})

    @server.tool()
    async def inspect_job(job_id: UUID) -> dict[str, Any]:
        """Inspect one job's known or uncertain outcome; access is checked on every invocation."""
        return await call("observe", "inspect", {"job_id": job_id})

    @server.tool()
    async def cancel_job(job_id: UUID) -> dict[str, Any]:
        """Cancel before action, or request cancellation while preserving a possibly completed action."""
        return await call("execute", "cancel", {"job_id": job_id})

    @server.tool()
    async def export_evidence(job_id: UUID, cursor: int = 0) -> dict[str, Any]:
        """Export one redacted evidence page with a content hash; follow next_cursor until null."""
        return await call("observe", "evidence", {"job_id": job_id, "cursor": cursor})

    return server


def main() -> None:
    create_server(load(McpAppSettings)).run(transport="stdio")


if __name__ == "__main__":
    main()
