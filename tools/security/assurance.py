"""Generate CycloneDX inventory, native dependency scan and unsigned SHA-256 provenance.

python -m tools.security.assurance tools/security/assurance.json
Only explicit manifest files are copied into the inventory staging directory. No credentials,
private memory, production snapshots or archives are inputs. Reports are private local artifacts.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class AssuranceConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")
    trivy: Path
    cache_dir: Path
    report_dir: Path
    source_roots: list[Path]
    provenance_roots: list[Path]
    excluded_parts: set[str]
    timeout_s: float = Field(gt=0)


def manifest(roots: list[Path], excluded: set[str]) -> dict[str, str]:
    hashes = {}
    for root in roots:
        for path in [root] if root.is_file() else sorted(root.rglob("*")) if root.exists() else []:
            if not path.is_file() or set(path.parts) & excluded or path.is_symlink():
                continue
            if (
                path.name == "CREDENTIALS.md"
                or path.name.startswith(".env")
                or path.suffix in {".key", ".pem", ".local", ".tfstate", ".tfvars"}
            ):
                continue
            hashes[path.as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
    return dict(sorted(hashes.items()))


def prepare(cfg: AssuranceConfig) -> Path:
    cfg.report_dir.mkdir(parents=True, exist_ok=True)
    staging = cfg.report_dir / "manifests"
    staging.mkdir(exist_ok=True)
    for path in cfg.source_roots:
        if not path.is_file() or path.name not in {"uv.lock", "package-lock.json"}:
            raise ValueError("only explicit dependency lockfiles may enter scan staging")
        target = staging / path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
    provenance = {
        "format": "fleetwright-sha256-provenance-v1",
        "signed": False,
        "created_utc": datetime.now(UTC).isoformat(),
        "limitations": "Local source inventory, not SLSA attestation or cryptographic signer identity.",
        "sha256": manifest(cfg.provenance_roots, cfg.excluded_parts),
    }
    (cfg.report_dir / "provenance.json").write_text(json.dumps(provenance, indent=2), encoding="utf-8")
    return staging


async def command(args: list[str], output: Path, timeout_s: float) -> dict[str, Any]:
    with output.open("wb") as log:
        process = await asyncio.create_subprocess_exec(*args, stdout=log, stderr=asyncio.subprocess.STDOUT)
        try:
            code = await asyncio.wait_for(process.wait(), timeout_s)
        except TimeoutError:
            process.kill()
            await process.wait()
            return {"exit_code": None, "status": "timeout", "log": output.as_posix()}
    return {"exit_code": code, "status": "passed" if code == 0 else "failed", "log": output.as_posix()}


async def main(config_path: Path) -> None:
    cfg = AssuranceConfig.model_validate_json(await asyncio.to_thread(config_path.read_text, encoding="utf-8"))
    staging = await asyncio.to_thread(prepare, cfg)
    common = [str(cfg.trivy), "fs", "--cache-dir", str(cfg.cache_dir), "--no-progress"]
    results = {}
    results["version"] = await command([str(cfg.trivy), "--version"], cfg.report_dir / "version.log", cfg.timeout_s)
    results["sbom"] = await command(
        [*common, "--format", "cyclonedx", "--output", str(cfg.report_dir / "sbom.cdx.json"), str(staging)],
        cfg.report_dir / "sbom.log",
        cfg.timeout_s,
    )
    results["dependencies"] = await command(
        [
            *common,
            "--scanners",
            "vuln",
            "--include-dev-deps",
            "--exit-code",
            "1",
            "--format",
            "json",
            "--output",
            str(cfg.report_dir / "dependencies.json"),
            str(staging),
        ],
        cfg.report_dir / "dependencies.log",
        cfg.timeout_s,
    )
    await asyncio.to_thread(
        (cfg.report_dir / "summary.json").write_text, json.dumps(results, indent=2), encoding="utf-8"
    )
    print(json.dumps(results), flush=True)
    if any(value["status"] != "passed" for value in results.values()):
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(main(Path(sys.argv[1])))
