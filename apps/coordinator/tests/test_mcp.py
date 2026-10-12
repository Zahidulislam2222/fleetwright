"""Real stdio MCP transport, including authorization rechecks on an already-open connection."""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from sqlalchemy import text
from test_workflows import proposal

from apikit import Api
from fw_core import workflows as jobs
from fw_core.db import tenant_tx

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]


async def test_real_stdio_submit_inspect_export_and_live_revocation(api: Api) -> None:
    access, job, user, token = await proposal(api)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "fw_mcp.server"],
        cwd=str(ROOT),
        env={**os.environ, "FW_MCP__TENANT_ID": str(api.tenant_id), "FW_MCP__ACCESS_TOKEN": token},
    )
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        names = {tool.name for tool in (await session.list_tools()).tools}
        assert names == {
            "workflow_contracts",
            "submit_workflow",
            "list_jobs",
            "inspect_job",
            "cancel_job",
            "export_evidence",
        }
        assert not (await session.call_tool("workflow_contracts", {})).isError
        async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
            account = await conn.scalar(
                text("SELECT account_id FROM workflow_jobs WHERE tenant_id=:t AND id=:j"),
                {"t": api.tenant_id, "j": UUID(job["id"])},
            )
        submitted = await session.call_tool(
            "submit_workflow",
            {
                "identity": uuid4().hex,
                "workflow": "service-request",
                "account_id": str(account),
                "inputs": {"reference": uuid4().hex, "title": "MCP demonstration", "priority": "normal"},
            },
        )
        assert not submitted.isError and submitted.structuredContent["state"] == "PENDING"
        key = submitted.structuredContent["id"]
        assert not (await session.call_tool("inspect_job", {"job_id": key})).isError
        exported = await session.call_tool("export_evidence", {"job_id": key})
        assert not exported.isError and exported.structuredContent["sha256"]
        assert (await session.call_tool("inspect_job", {"job_id": str(uuid4())})).isError
        async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
            await jobs.revoke_access(conn, api.tenant_id, access.grant, user)
        for name, arguments in [
            ("workflow_contracts", {}),
            ("list_jobs", {}),
            ("inspect_job", {"job_id": key}),
            ("cancel_job", {"job_id": key}),
            ("export_evidence", {"job_id": key}),
        ]:
            assert (await session.call_tool(name, arguments)).isError


async def test_stdio_observation_grant_rejects_execution(api: Api) -> None:
    _access, _job, user, _token = await proposal(api)
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        _grant, token = await jobs.issue_access(conn, api.tenant_id, user, frozenset({"observe"}), 3600)
    params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "fw_mcp.server"],
        cwd=str(ROOT),
        env={**os.environ, "FW_MCP__TENANT_ID": str(api.tenant_id), "FW_MCP__ACCESS_TOKEN": token},
    )
    async with stdio_client(params) as (reader, writer), ClientSession(reader, writer) as session:
        await session.initialize()
        assert not (await session.call_tool("list_jobs", {})).isError
        assert (await session.call_tool("cancel_job", {"job_id": str(uuid4())})).isError
