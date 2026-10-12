"""Run the real suite in separate local databases; never reset the development databases.

Usage: python tools/dev/run_tests.py [pytest arguments]. Creates missing test databases using the
local Compose administrator, migrates with fw_owner, and propagates isolated DSNs to subprocesses.
"""

from __future__ import annotations

import asyncio
import os
import re
import shutil
import sys
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
from dotenv import dotenv_values
from pydantic import BaseModel, ConfigDict, Field

from fw_core.data import load_yaml

ROOT = Path(__file__).resolve().parents[2]


class TestDatabases(BaseModel):
    model_config = ConfigDict(extra="forbid")
    coordinator_database: str = Field(pattern="^[a-z_]+_test$")
    board_database: str = Field(pattern="^[a-z_]+_test$")


async def environment() -> dict[str, str]:
    values = {k: v for k, v in dotenv_values(ROOT / ".env").items() if v is not None}
    cfg = load_yaml(ROOT / "config", "testing.yaml", TestDatabases)
    owner = urlsplit(values["FW_OWNER_DB__DSN"])
    if owner.hostname not in {"localhost", "127.0.0.1"}:
        raise RuntimeError("test harness refuses non-local databases")
    conn = await asyncpg.connect(
        host=owner.hostname,
        port=owner.port,
        user="postgres",
        database="postgres",
        password=values["FWDEV_PG_SUPERUSER_PASSWORD"],
    )
    try:
        for name, role in [(cfg.coordinator_database, "fw_owner"), (cfg.board_database, "fw_board")]:
            if not await conn.fetchval("SELECT 1 FROM pg_database WHERE datname=$1", name):
                # Both identifiers are validated, and roles are fixed protocol names.
                await conn.execute(f'CREATE DATABASE "{name}" OWNER {role}')
        await conn.execute(f'REVOKE ALL ON DATABASE "{cfg.coordinator_database}" FROM PUBLIC')
        await conn.execute(f'GRANT CONNECT ON DATABASE "{cfg.coordinator_database}" TO fw_app, fw_worker')
    finally:
        await conn.close()
    conn = await asyncpg.connect(
        host=owner.hostname,
        port=owner.port,
        user="postgres",
        database=cfg.coordinator_database,
        password=values["FWDEV_PG_SUPERUSER_PASSWORD"],
    )
    try:
        await conn.execute("REVOKE ALL ON SCHEMA public FROM PUBLIC")
        await conn.execute("GRANT USAGE ON SCHEMA public TO fw_app,fw_worker")
        await conn.execute("ALTER SCHEMA public OWNER TO fw_owner")
    finally:
        await conn.close()
    env = dict(os.environ)
    for key in ["FW_OWNER_DB__DSN", "FW_APP_DB__DSN", "FW_WORKER_DB__DSN", "FW_BOARD_DB__DSN"]:
        parts = urlsplit(values[key])
        name = cfg.board_database if key == "FW_BOARD_DB__DSN" else cfg.coordinator_database
        env[key] = urlunsplit(parts._replace(path="/" + name))
    env["FW_ENVIRONMENT"] = "test"
    git = shutil.which("git")
    if git is None:
        raise RuntimeError("Git is required to verify private recovery files")
    checked = await asyncio.create_subprocess_exec(git, "check-ignore", "--quiet", "CREDENTIALS.md", cwd=ROOT)
    if await checked.wait():
        raise RuntimeError("CREDENTIALS.md must be ignored")
    recovery = ROOT / "CREDENTIALS.md"
    private = recovery.read_text(encoding="utf-8")
    private = re.sub(r"# Last updated: .*", "# Last updated: 2026-10-13", private)
    marker = "\n## Isolated test databases\n"
    if marker not in private:
        private += marker + "\n| Key | Value |\n|---|---|\n"
        private += "\n".join(f"| {k} | {env[k]} |" for k in env if k.startswith("FW_") and k.endswith("__DSN")) + "\n"
        recovery.write_text(private, encoding="utf-8")
    return env


async def main() -> None:
    env = await environment()
    coordinator_dsn = env["FW_OWNER_DB__DSN"].replace("postgresql+asyncpg:", "postgresql:")
    lock = await asyncpg.connect(coordinator_dsn)
    try:
        await lock.execute("SELECT pg_advisory_lock(hashtext('fleetwright-test-suite'))")
        migration = await asyncio.create_subprocess_exec(
            sys.executable, "-m", "fw_coordinator.migrate", cwd=ROOT, env=env
        )
        if await migration.wait():
            raise RuntimeError("test migration failed")
        print("Running suite against isolated local test databases (development data preserved).", flush=True)
        result = await asyncio.create_subprocess_exec(sys.executable, "-m", "pytest", *sys.argv[1:], cwd=ROOT, env=env)
        raise SystemExit(await result.wait())
    finally:
        await lock.close()


if __name__ == "__main__":
    asyncio.run(main())
