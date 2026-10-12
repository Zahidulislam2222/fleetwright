"""Private, verified Postgres backup and non-destructive restoration drill.

Host-side command using the existing Docker CLI. Credentials remain inside Postgres; no password
in command arguments. Scheduled mode creates backups only. Restoration is restricted to fresh
databases ending in _restore_test and never drops an existing database.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import shutil
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from uuid import uuid4

from fw_core.settings import BackupAppSettings, BackupSettings, load


def command(cfg: BackupSettings, args: list[str], data: bytes | None = None) -> bytes:
    return asyncio.run(_command(cfg, args, data))


async def _command(cfg: BackupSettings, args: list[str], data: bytes | None) -> bytes:
    executable = shutil.which(cfg.executable)
    if executable is None:
        raise RuntimeError("configured backup executable is unavailable")
    process = await asyncio.create_subprocess_exec(
        executable,
        "exec",
        "-i",
        cfg.container,
        *args,
        stdin=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    try:
        stdout, _stderr = await asyncio.wait_for(process.communicate(data), cfg.timeout_s)
    except TimeoutError:
        process.kill()
        await process.communicate()
        raise
    if process.returncode:
        # Server errors can contain SQL or sensitive row values. Keep them out of console/logs.
        raise RuntimeError("backup/restore command failed; inspect database service privately")
    return stdout


def create(cfg: BackupSettings) -> Path:
    cfg.directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid4().hex[:8]
    folder = cfg.directory / stamp
    folder.mkdir(mode=0o700)
    metadata: dict[str, object] = {"created_at": datetime.now(UTC).isoformat(), "databases": {}}
    records = {}
    for database in cfg.databases:
        data = command(cfg, ["pg_dump", "-U", cfg.username, "-Fc", database])
        if not data.startswith(b"PGDMP"):
            raise RuntimeError("invalid or empty PostgreSQL archive")
        command(cfg, ["pg_restore", "--list"], data)
        temporary = folder / (database + ".dump.tmp")
        with temporary.open("xb") as output:
            output.write(data)
            output.flush()
            os.fsync(output.fileno())
        os.replace(temporary, folder / (database + ".dump"))
        records[database] = {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
    metadata["databases"] = records
    (folder / "manifest.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    # Retain prior valid backups. A failed new backup never removes the last good copy.
    completed = sorted(p for p in cfg.directory.iterdir() if p.is_dir() and (p / "manifest.json").is_file())
    for old in completed[: -cfg.retention_count]:
        # Delete only the exact generated archive files listed by configuration, never arbitrary paths.
        for database in cfg.databases:
            archive = old / (database + ".dump")
            if archive.is_file() and not archive.is_symlink():
                archive.unlink()
        manifest = old / "manifest.json"
        if not manifest.is_symlink():
            manifest.unlink()
        if not any(old.iterdir()):
            old.rmdir()
    return folder


def drill(cfg: BackupSettings, folder: Path) -> dict[str, object]:
    metadata = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    report: dict[str, object] = {}
    for database in cfg.databases:
        data = (folder / (database + ".dump")).read_bytes()
        if hashlib.sha256(data).hexdigest() != metadata["databases"][database]["sha256"]:
            raise RuntimeError("archive integrity mismatch; restore refused")
        target = database + "_" + uuid4().hex[:8] + "_restore_test"
        command(cfg, ["createdb", "-U", cfg.username, target])  # refuses any existing database
        command(cfg, ["pg_restore", "-U", cfg.username, "--exit-on-error", "-d", target], data)
        restored = command(
            cfg,
            [
                "psql",
                "-U",
                cfg.username,
                "-d",
                target,
                "-Atc",
                "SELECT count(*) FROM pg_tables WHERE schemaname='public'",
            ],
        )
        report[database] = {
            "restored_database": target,
            "public_tables": int(restored.strip()),
            "sha256": hashlib.sha256(data).hexdigest(),
        }
    (folder / "restore-report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    cfg = load(BackupAppSettings).backup
    operation = sys.argv[1] if len(sys.argv) > 1 else "create"
    if operation == "create":
        folder = create(cfg)
        print(f"Verified private backup: {folder}")
    elif operation == "drill" and len(sys.argv) == 3:
        report = drill(cfg, Path(sys.argv[2]))
        print(f"Restored {len(report)} databases; private report saved alongside backup.")
    elif operation == "loop":
        while True:
            create(cfg)
            time.sleep(cfg.interval_s)
    else:
        raise SystemExit("Usage: python -m fw_coordinator.backup create|loop|drill <backup-folder>")


if __name__ == "__main__":
    main()
