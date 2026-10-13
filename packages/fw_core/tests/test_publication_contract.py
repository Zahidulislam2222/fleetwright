"""Public release contract regression checks; safe without services."""

import json
import re
from pathlib import Path, PurePosixPath

import yaml
from dotenv import dotenv_values

from fw_coordinator.demo import load_demo
from fw_core.settings import BackupAppSettings, WorkerSettings, WorkflowSettings

ROOT = Path(__file__).resolve().parents[3]
BANNED = re.compile(r"\b(demo|demonstration|prototype|fictional|fictitious|simulated|illustrative|mock)\b", re.I)


def strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for item in value.values():
            yield from strings(item)
    elif isinstance(value, list):
        for item in value:
            yield from strings(item)


def test_visible_product_copy():
    paths = ROOT.glob("apps/dashboard/src/content/*.json")
    failures = []
    for path in paths:
        for value in strings(json.loads(path.read_text(encoding="utf-8"))):
            # Paths/URLs are stable compatibility identifiers, not display prose.
            if value.startswith(("/", "http:", "https:")):
                continue
            if BANNED.search(value):
                failures.append(f"{path.name}: {value}")
    assert not failures, "\n".join(failures)


def test_release_contains_workflow_runner_and_backup_service():
    compose = (ROOT / "deploy/templates/compose.yaml").read_text()
    assert "  workflow-worker:" in compose
    assert '"fw_worker.workflows"' in compose
    config = json.loads((ROOT / "deploy/deploy.config.json").read_text())
    values = {
        **config,
        **config["limits"],
        **config["backend"],
        "releaseId": "20261013-validation",
        "postgresImage": "postgres:test",
        "redisImage": "redis:test",
        "mailpitImage": "mailpit:test",
    }
    rendered = re.sub(r"\{\{(\w+)\}\}", lambda match: str(values[match[1]]), compose)
    services = yaml.safe_load(rendered)["services"]
    longest_drain = max(WorkerSettings(cell="test").drain_timeout_s, WorkflowSettings().drain_timeout_s)
    for service in ("worker", "workflow-worker", "crawler"):
        grace = services[service].get("stop_grace_period")
        assert grace is not None, f"{service} has no explicit shutdown allowance"
        seconds = float(grace.removesuffix("s"))
        assert seconds == config["backend"]["workerStopGraceS"]
        assert seconds > longest_drain, f"{service} shutdown interrupts a configured browser drain"
    unit = (ROOT / "deploy/templates/backup.service").read_text()
    assert "fw_coordinator.backup loop" in unit
    assert "UMask=0077" in unit
    assert "Restart=on-failure" in unit
    builder = (ROOT / "deploy/build-release.mjs").read_text()
    assert '"apps/dashboard"' in builder
    assert '"deploy/templates"' in builder


def test_backup_template_supplies_required_settings(tmp_path):
    config = json.loads((ROOT / "deploy/deploy.config.json").read_text())
    values = {**config, **config["backup"], "releaseId": "20261013-validation"}
    values["backupDatabases"] = json.dumps(config["backup"]["backupDatabases"])
    values["buildDirectory"] = str(PurePosixPath(config["releaseRoot"]).parent / "build" / values["releaseId"])
    template = (ROOT / "deploy/templates/backup.env").read_text()
    rendered = re.sub(r"\{\{(\w+)\}\}", lambda match: str(values[match[1]]), template)
    path = tmp_path / "backup.env"
    path.write_text(rendered)
    cfg = BackupAppSettings(_env_file=path)
    assert cfg.backup.username
    assert cfg.backup.databases
    assert all(value is not None for value in dotenv_values(path).values())


def test_backup_service_paths_are_absolute_and_normalized():
    config = json.loads((ROOT / "deploy/deploy.config.json").read_text())
    values = {**config, **config["backup"], "releaseId": "20261013-validation"}
    values["buildDirectory"] = str(PurePosixPath(config["releaseRoot"]).parent / "build" / values["releaseId"])
    unit = (ROOT / "deploy/templates/backup.service").read_text()
    rendered = re.sub(r"\{\{(\w+)\}\}", lambda match: str(values[match[1]]), unit)
    for key in ("WorkingDirectory", "ExecStart"):
        value = re.search(rf"^{key}=(\S+)", rendered, re.M)[1]
        assert PurePosixPath(value).is_absolute()
        assert ".." not in PurePosixPath(value).parts


def test_seed_workflow_pool_is_reserved_in_release_and_local_settings():
    pool = load_demo(ROOT / "config").seed.workflow_pool
    for path in [ROOT / ".env.example", ROOT / "deploy/env/fleetwright.env.example"]:
        values = dotenv_values(path)
        groups = json.loads(values["FW_WORKER__RESERVED_ACCOUNT_GROUPS"])
        cfg = WorkerSettings(cell="test-cell", reserved_account_groups=groups)
        assert pool.group in cfg.reserved_account_groups
    assert pool.prefix != load_demo(ROOT / "config").seed.board_account_prefix


def test_documentation_links_and_required_topics():
    required = [
        "product.md",
        "integrations.md",
        "maintenance.md",
        "operations/deployment.md",
        "scaling/capacity-model.md",
        "scaling/slo.md",
        "legal/README.md",
        "legal/privacy.md",
        "security/controls.md",
        "roadmap.md",
    ]
    index = (ROOT / "docs/README.md").read_text()
    for path in required:
        assert (ROOT / "docs" / path).is_file(), path
        assert path in index, path
    for path in [ROOT / "README.md", *ROOT.glob("docs/**/*.md")]:
        for target in re.findall(r"\]\(([^)#]+)(?:#[^)]*)?\)", path.read_text(encoding="utf-8")):
            if "://" not in target and not target.startswith("mailto:"):
                assert (path.parent / target).exists(), f"{path}: {target}"
