"""Real backup/restore proof in a separate PostgreSQL cluster bootstrapped from repository roles."""

from __future__ import annotations

import asyncio
import json
import shutil
from pathlib import Path
from uuid import UUID, uuid4

import pytest
import yaml
from sqlalchemy import text
from test_workflows import approved

from apikit import Api
from fw_coordinator.backup import command, create, drill
from fw_core.db import tenant_tx
from fw_core.settings import BackupSettings

ROOT = Path(__file__).resolve().parents[3]
pytestmark = pytest.mark.integration


async def test_backup_restores_approved_job_and_audit_into_fresh_cluster(api: Api, tmp_path: Path) -> None:
    _access, job, _user, _token = await approved(api)
    tenant, key = api.tenant_id, UUID(job["id"])
    sql = """SELECT md5(row_to_json(j)::text) FROM workflow_jobs j WHERE tenant_id=:t AND id=:j"""
    async with tenant_tx(api.app.state.services.engine, tenant) as conn:
        before_hash = await conn.scalar(text(sql), {"t": tenant, "j": key})
        before_events = await conn.scalar(
            text("SELECT count(*) FROM workflow_events WHERE tenant_id=:t AND job_id=:j"), {"t": tenant, "j": key}
        )
    cfg = BackupSettings(
        directory=ROOT / "var" / "restore-drills",
        container="fleetwright-local-postgres-1",
        executable="docker",
        username="postgres",
        databases=["fleetwright_test", "mockboard_test"],
    )
    folder = await asyncio.to_thread(create, cfg)
    executable = shutil.which("docker")
    assert executable
    image = yaml.safe_load((ROOT / "infra/compose/local.yaml").read_text())["services"]["postgres"]["image"]
    container = "fleetwright-restore-test-" + uuid4().hex[:12]
    # Keep the image's temporary socket-only server observable, so a socket readiness
    # check cannot accidentally pass this regression by missing the initialization window.
    initialization = tmp_path / "readiness.sql"
    initialization.write_text("SELECT pg_sleep(5);", encoding="utf-8")

    async def docker(*arguments: str, data: bytes | None = None) -> bytes:
        process = await asyncio.create_subprocess_exec(
            executable,
            *arguments,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout, _stderr = await asyncio.wait_for(process.communicate(data), 120)
        assert process.returncode == 0, "restore drill Docker command failed"
        return stdout

    await docker(
        "run",
        "--pull=never",
        "--rm",
        "-d",
        "--name",
        container,
        "--network",
        "none",
        "--memory",
        "512m",
        "--mount",
        f"type=bind,source={initialization},target=/docker-entrypoint-initdb.d/readiness.sql,readonly",
        "-e",
        "POSTGRES_PASSWORD=test-key",
        image,
    )
    try:
        async with asyncio.timeout(60):
            while True:
                probe = await asyncio.create_subprocess_exec(
                    executable,
                    "exec",
                    container,
                    "pg_isready",
                    "-h",
                    "127.0.0.1",
                    "-U",
                    "postgres",
                    stdout=asyncio.subprocess.DEVNULL,
                    stderr=asyncio.subprocess.DEVNULL,
                )
                if await probe.wait() == 0:
                    break
                await asyncio.sleep(0.2)
        # Only the final server listens on TCP; the temporary initializer must not count.
        await docker("exec", container, "pg_isready", "-h", "127.0.0.1", "-U", "postgres")
        await docker(
            "exec",
            "-i",
            "-e",
            "POSTGRES_USER=postgres",
            "-e",
            "FWDEV_PG_OWNER_PASSWORD=test-key",
            "-e",
            "FWDEV_PG_APP_PASSWORD=test-key",
            "-e",
            "FWDEV_PG_WORKER_PASSWORD=test-key",
            "-e",
            "FWDEV_PG_BOARD_PASSWORD=test-key",
            container,
            "sh",
            data=(ROOT / "infra/postgres/10-roles.sh").read_bytes(),
        )
        restored_cfg = cfg.model_copy(update={"container": container})
        report = await asyncio.to_thread(drill, restored_cfg, folder)
        restored = report["fleetwright_test"]["restored_database"]
        query = """SELECT md5(row_to_json(j)::text) FROM workflow_jobs j WHERE tenant_id=:'tenant' AND id=:'job';
            SELECT count(*) FROM workflow_events WHERE tenant_id=:'tenant' AND job_id=:'job';
            SELECT count(*) FROM workflow_approvals WHERE tenant_id=:'tenant' AND job_id=:'job';
            SELECT count(*) FROM audit_log WHERE tenant_id=:'tenant' AND target=:'job';"""
        checks = (
            (
                await asyncio.to_thread(
                    command,
                    restored_cfg,
                    ["psql", "-U", "postgres", "-d", restored, "-At", "-v", f"tenant={tenant}", "-v", f"job={key}"],
                    query.encode(),
                )
            )
            .decode()
            .splitlines()
        )
        assert checks[0] == before_hash
        assert int(checks[1]) == before_events
        assert int(checks[2]) == 1 and int(checks[3]) >= 2
        integrity = {
            "job_hash_preserved": True,
            "events_preserved": True,
            "approval_preserved": True,
            "audit_preserved": True,
            "fresh_cluster_roles_bootstrapped": True,
            "network": "none",
        }
        (folder / "invariants.json").write_text(json.dumps(integrity, indent=2), encoding="utf-8")
    finally:
        await docker("stop", container)
