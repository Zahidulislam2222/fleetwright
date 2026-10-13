"""Operational acceptance: failures/recovery are durable; off-host archives authenticate every byte."""

from __future__ import annotations

import asyncio
import base64
import hashlib
import json
import sys
import time
from pathlib import Path
from uuid import UUID, uuid4

import httpx
import pytest
from cryptography.exceptions import InvalidTag
from pydantic import SecretStr

from fw_coordinator import monitor as monitoring
from fw_coordinator.monitor import ObservationGrant, check, cycle, database, record, report
from fw_coordinator.recovery import open_bundle, protect, unpack
from fw_core.settings import MonitorAppSettings, MonitorSettings, RecoverySettings


def monitor(tmp_path: Path) -> MonitorSettings:
    return MonitorSettings(
        database=tmp_path / "monitor.db",
        notification_file=tmp_path / "notices.json",
        probes=[{"name": "owned", "url": "https://owned.test/health"}],
        failures_before_alert=2,
    )


async def test_failure_recovery_persists_across_monitor_restart(tmp_path: Path) -> None:
    cfg = monitor(tmp_path)
    conn = database(cfg)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(503))) as client:
        await cycle(cfg, conn, client)
        await cycle(cfg, conn, client)
    assert report(cfg, conn)["failures"] == 1
    conn.close()
    conn = database(cfg)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200))) as client:
        await cycle(cfg, conn, client)
    assert [x["kind"] for x in json.loads(cfg.notification_file.read_text())] == ["recovered", "failed"]
    assert report(cfg, conn)["failures"] == 0
    conn.close()


async def test_monitor_authentication_and_response_bound(tmp_path: Path) -> None:
    cfg = monitor(tmp_path)
    cfg.probes[0].bearer_token = SecretStr("test-key")
    cfg.probes[0].tenant_id = "test-tenant"

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.headers["Authorization"] == "Bearer test-key"
        assert request.headers["X-Fleetwright-Tenant"] == "test-tenant"
        return httpx.Response(200, text="fleetwright_workflow_alerts 1\n")

    conn = database(cfg)
    async with httpx.AsyncClient(transport=httpx.MockTransport(handler)) as client:
        await cycle(cfg, conn, client)
    assert conn.execute("SELECT reason FROM checks").fetchone()[0] == "workflow_alert"
    record(cfg, conn, "owned", False, 0, "workflow_alert")
    assert "test-key" not in cfg.notification_file.read_text()
    conn.close()


def files() -> dict[str, bytes]:
    data = b"PGDMP" + b"test-database-content"
    return {
        "owned.dump": data,
        "manifest.json": json.dumps(
            {"databases": {"owned": {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}}}
        ).encode(),
    }


def recovery(tmp_path: Path) -> RecoverySettings:
    return RecoverySettings(
        directory=tmp_path / "offhost", master_key_b64=base64.b64encode(bytes(32)).decode(), key_id="test-key"
    )


def test_encrypted_copy_roundtrip_tamper_and_wrong_key(tmp_path: Path) -> None:
    cfg = recovery(tmp_path)
    target = protect(cfg, files())
    assert b"test-database-content" not in target.read_bytes()
    assert open_bundle(cfg, target) == files()
    unpack(cfg, target, tmp_path / "fresh")
    assert (tmp_path / "fresh/owned.dump").read_bytes() == files()["owned.dump"]
    wrong = cfg.model_copy(
        update={"master_key_b64": type(cfg.master_key_b64)(base64.b64encode(bytes([1]) * 32).decode())}
    )
    with pytest.raises(InvalidTag):
        open_bundle(wrong, target)
    damaged = bytearray(target.read_bytes())
    damaged[-1] ^= 1
    target.write_bytes(damaged)
    with pytest.raises(InvalidTag):
        open_bundle(cfg, target)


def test_invalid_copy_does_not_remove_last_good_archive(tmp_path: Path) -> None:
    cfg = recovery(tmp_path)
    target = protect(cfg, files())
    bad = files()
    bad["../escape"] = b"bad"
    with pytest.raises(ValueError):
        protect(cfg, bad)
    assert target.exists()
    assert open_bundle(cfg, target) == files()


@pytest.mark.parametrize("value", ["NaN", "inf", "-1", "1\nfleetwright_workflow_alerts 0"])
async def test_malformed_metrics_fail_closed_without_persisting_input(tmp_path: Path, value: str) -> None:
    cfg = monitor(tmp_path)
    cfg.probes[0].bearer_token = SecretStr("test-key")
    conn = database(cfg)
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, text=f"fleetwright_workflow_alerts {value}\n"))
    ) as client:
        await cycle(cfg, conn, client)
    assert conn.execute("SELECT healthy,reason FROM checks").fetchone() == (0, "invalid_metrics")
    conn.close()


async def test_metrics_persist_only_allowlisted_numeric_values(tmp_path: Path) -> None:
    cfg = monitor(tmp_path)
    cfg.probes[0].bearer_token = SecretStr("test-key")
    body = 'fleetwright_workflow_alerts 0\nfleetwright_workflow_jobs{state="CONFIRMED"} 2\nprivate_secret 991\n'
    conn = database(cfg)
    async with httpx.AsyncClient(transport=httpx.MockTransport(lambda _: httpx.Response(200, text=body))) as client:
        await cycle(cfg, conn, client)
    metrics = dict(conn.execute("SELECT name,value FROM metrics"))
    assert metrics == {"fleetwright_workflow_alerts": 0, 'fleetwright_workflow_jobs{state="CONFIRMED"}': 2}
    assert report(cfg, conn)["latest_metrics"]["owned"] == metrics
    assert "private_secret" not in cfg.notification_file.read_text()
    conn.close()


async def test_response_limit_and_retention(tmp_path: Path) -> None:
    cfg = monitor(tmp_path)
    conn = database(cfg)
    with conn:
        conn.execute("INSERT INTO checks VALUES(NULL,?,?,?,?,?)", (0, "old", 1, 0, "healthy"))
        conn.execute("INSERT INTO notifications VALUES(NULL,?,?,?)", (0, "old", "failed"))
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, content=b"x" * (cfg.response_max_bytes + 1)))
    ) as client:
        await cycle(cfg, conn, client)
    assert conn.execute("SELECT reason FROM checks").fetchall() == [("response_limit",)]
    assert conn.execute("SELECT count(*) FROM notifications").fetchone()[0] == 0
    conn.close()


def test_recovery_rejects_malformed_manifest_without_pruning(tmp_path: Path) -> None:
    cfg = recovery(tmp_path)
    good = protect(cfg, files())
    for manifest in ([], {"databases": []}, {"databases": {"": {}}}, {"databases": {"owned": {"bytes": True}}}):
        invalid = files()
        invalid["manifest.json"] = json.dumps(manifest).encode()
        with pytest.raises(ValueError):
            protect(cfg, invalid)
        assert open_bundle(cfg, good) == files()


def test_retention_keeps_latest_verified_copy_and_protects_symlink(tmp_path: Path) -> None:
    cfg = recovery(tmp_path).model_copy(update={"retention_count": 2})
    first = protect(cfg, files())
    time.sleep(0.01)
    second = protect(cfg, files())
    third = protect(cfg, files())
    assert not first.exists() and second.exists() and third.exists()
    alias = cfg.directory / "alias.fwrecovery"
    try:
        alias.symlink_to(third.name)
    except OSError:
        return  # Windows user may not have symlink privilege; other assertions still apply.
    with pytest.raises(ValueError):
        open_bundle(cfg, alias)


def grant_config(tmp_path: Path) -> MonitorAppSettings:
    return MonitorAppSettings(
        _env_file=None,
        environment="test",
        config_dir=tmp_path,
        monitor=monitor(tmp_path),
        app_db={"dsn": "postgresql+asyncpg://test-key@owned.test/test"},
        monitor_grant={"tenant_id": uuid4(), "user_id": uuid4(), "token_file": tmp_path / "grant.json"},
    )


async def test_observation_grant_renewal_and_restart_bind_predecessor(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = grant_config(tmp_path)
    assert cfg.monitor_grant is not None
    cfg.monitor.probes[0].bearer_token = SecretStr("test-key")
    seen = []

    async def authority(_, grant, predecessor):
        seen.append(predecessor)
        return {"grant_id": str(uuid4()), "token": "test-key_" * 4, "tenant_id": str(grant.tenant_id)}

    monkeypatch.setattr(monitoring, "issue", authority)
    instance = ObservationGrant(cfg)
    await instance.ensure()
    first = instance.identifier
    await instance.ensure()
    assert seen == [None]
    instance.renew_at = 0
    await instance.ensure()
    assert seen == [None, first]
    second = instance.identifier
    assert json.loads(cfg.monitor_grant.token_file.read_text())["grant_id"] == str(second)
    assert cfg.monitor.probes[0].tenant_id == str(cfg.monitor_grant.tenant_id)
    restarted = ObservationGrant(cfg)
    await restarted.ensure()
    assert seen == [None, first, second]
    assert UUID(json.loads(cfg.monitor_grant.token_file.read_text())["grant_id"]) == restarted.identifier


@pytest.mark.parametrize("payload", ["not-json", '{"token":"test-key"}', '{"grant_id":"bad"}'])
async def test_malformed_authority_preserves_previous_recovery_file(tmp_path: Path, payload: str) -> None:
    cfg = grant_config(tmp_path)
    assert cfg.monitor_grant is not None
    initial = {"grant_id": str(uuid4()), "token": "test-key_" * 4, "tenant_id": str(cfg.monitor_grant.tenant_id)}
    cfg.monitor_grant.token_file.write_text(json.dumps(initial))
    cfg.monitor_grant.authority_command = [sys.executable, "-c", "import sys;sys.stdout.write(" + repr(payload) + ")"]
    with pytest.raises(ValueError):
        await ObservationGrant(cfg).ensure()
    assert json.loads(cfg.monitor_grant.token_file.read_text()) == initial


async def test_once_fails_on_first_bad_probe_before_alert_threshold(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    cfg = monitor(tmp_path)
    settings = tmp_path / "monitor.json"
    settings.write_text(
        json.dumps({"environment": "test", "config_dir": str(tmp_path), "monitor": cfg.model_dump(mode="json")})
    )
    original_client = httpx.AsyncClient
    monkeypatch.setattr(
        monitoring.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(lambda _: httpx.Response(503))),
    )
    monkeypatch.setattr(sys, "argv", ["monitor", "once", "--settings-file", str(settings)])
    with pytest.raises(SystemExit) as stopped:
        await monitoring.main()
    assert stopped.value.code == 1
    with database(cfg) as conn:
        assert report(cfg, conn)["failures"] == 0
        assert report(cfg, conn)["latest_checks"][0]["healthy"] == 0
    conn.close()


async def test_slow_response_cannot_extend_total_probe_deadline(tmp_path: Path) -> None:
    class SlowStream(httpx.AsyncByteStream):
        async def __aiter__(self):
            for _ in range(100):
                await asyncio.sleep(0.01)
                yield b"x"

    cfg = monitor(tmp_path).model_copy(update={"timeout_s": 0.025})
    async with httpx.AsyncClient(
        transport=httpx.MockTransport(lambda _: httpx.Response(200, stream=SlowStream()))
    ) as client:
        result = await check(client, cfg, cfg.probes[0])
    assert result.reason == "transport_or_format" and not result.healthy
    assert result.elapsed_ms < 500


def test_published_independent_uptime_configuration_is_valid() -> None:
    root = Path(__file__).resolve().parents[3]
    cfg = MonitorAppSettings(_env_file=None, **json.loads((root / "config/uptime.json").read_text()))
    assert cfg.monitor_grant is None and len(cfg.monitor.probes) == 2
    assert all(probe.url.startswith("https://") and probe.bearer_token is None for probe in cfg.monitor.probes)


async def test_loop_surfaces_new_notification_when_retention_reuses_id(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    class StopAfterTwoCycles(Exception):
        pass

    cfg = monitor(tmp_path).model_copy(
        update={
            "failures_before_alert": 1,
            "retention_days": 1,
            "probes": [
                monitoring.ProbeSettings(name="owned_a", url="https://owned.test/a"),
                monitoring.ProbeSettings(name="owned_b", url="https://owned.test/b"),
            ],
        }
    )
    settings = tmp_path / "loop.json"
    settings.write_text(
        json.dumps({"environment": "test", "config_dir": str(tmp_path), "monitor": cfg.model_dump(mode="json")})
    )
    clock = [1_000_000.0]
    monkeypatch.setattr(monitoring.time, "time", lambda: clock[0])
    original_client = httpx.AsyncClient

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503 if request.url.path == "/a" or clock[0] > 1_000_000 else 200)

    monkeypatch.setattr(
        monitoring.httpx,
        "AsyncClient",
        lambda **kwargs: original_client(**kwargs, transport=httpx.MockTransport(handler)),
    )

    async def advance_or_stop(_: float) -> None:
        if clock[0] > 1_000_000:
            raise StopAfterTwoCycles
        clock[0] += 2 * 86400

    monkeypatch.setattr(monitoring.asyncio, "sleep", advance_or_stop)
    monkeypatch.setattr(sys, "argv", ["monitor", "loop", "--settings-file", str(settings)])
    with pytest.raises(StopAfterTwoCycles):
        await monitoring.main()
    reports = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert len(reports) == 2
    assert reports[0]["notifications"][0]["name"] == "owned_a"
    assert reports[1]["notifications"][0]["name"] == "owned_b"


def test_configured_notice_limit_bounds_sink_and_report_without_losing_history(tmp_path: Path) -> None:
    cfg = monitor(tmp_path).model_copy(update={"notification_limit": 1, "failures_before_alert": 1})
    conn = database(cfg)
    record(cfg, conn, "owned", False, 0, "http_status")
    record(cfg, conn, "owned", True, 0, "healthy")
    record(cfg, conn, "owned", False, 0, "http_status")
    assert conn.execute("SELECT count(*) FROM notifications").fetchone()[0] == 3
    assert len(json.loads(cfg.notification_file.read_text())) == 1
    summary = report(cfg, conn)["notifications"]
    assert len(summary) == 1 and summary[0]["kind"] == "failed"
    conn.close()
