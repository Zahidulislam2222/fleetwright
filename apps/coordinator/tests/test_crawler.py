"""Crawler acceptance: real HTTP/data, layout alarms, fences, retention, RBAC and SSRF."""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import json
import socket
import time
from pathlib import Path
from uuid import UUID, uuid4

import pytest
from sqlalchemy import text

from apikit import Api
from boardkit import Board
from dbkit import Db, new_tenant
from fw_coordinator.crawl_contracts import FieldSpec, definitions, extract
from fw_coordinator.crawl_http import EgressDenied, addresses, fetch, validate_url
from fw_coordinator.crawls import Crawler, submit
from fw_core.db import tenant_tx
from fw_core.settings import CrawlAppSettings


def runner(api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Crawler:
    cfg = api.cfg.crawl.model_copy(
        update={"output_directory": tmp_path, "domain_delay_s": 0, "poll_s": 0.01, "retry_base_s": 0.01}
    )
    monkeypatch.setattr(api.app.state.services.cfg, "crawl", cfg)
    return Crawler(
        CrawlAppSettings(
            environment="test",
            config_dir=api.cfg.config_dir,
            app_db=api.cfg.app_db,
            board_client=api.cfg.board_client,
            crawl=cfg,
        ),
        api.app.state.services.engine,
    )


@pytest.mark.parametrize(
    "url",
    [
        "http://other.test/a",
        "file:///etc/passwd",
        "http://user:pass@owned.test/a",
        "http://owned.test/a#b",
        "http://owned.test/\\evil",
        "http://owned.test/a\r\nb",
    ],
)
def test_ambiguous_and_unapproved_origins_rejected(url: str) -> None:
    with pytest.raises(EgressDenied):
        validate_url(url, "http://owned.test")


@pytest.mark.parametrize(
    "address", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:127.0.0.1", str(ipaddress.IPv4Address(0))]
)
def test_private_and_metadata_dns_blocked(monkeypatch: pytest.MonkeyPatch, address: str) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(0, 0, 0, "", (address, 80))])
    with pytest.raises(EgressDenied):
        addresses("owned.test", 80, False)


def test_owned_exception_never_allows_metadata(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(socket, "getaddrinfo", lambda *_args, **_kwargs: [(0, 0, 0, "", ("169.254.169.254", 80))])
    with pytest.raises(EgressDenied):
        addresses("owned.test", 80, True)


@pytest.mark.integration
async def test_real_crawl_export_layout_alarm_restart_fence_and_retention(
    api: Api, board: Board, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    crawler = runner(api, tmp_path, monkeypatch)
    tenant = api.tenant_id
    owner = await api.signed_in("owner")
    async with contextlib.aclosing(owner):
        response = await owner.post("/v1/crawls/jobs", json={"definition": "owned-catalogue"})
        assert response.status_code == 201, response.text
        first = UUID(response.json()["id"])
        assert (await owner.post("/v1/crawls/jobs", json={"definition": "owned-catalogue"})).status_code == 409
        job = await crawler.lease(tenant)
        assert job is not None
        assert await crawler.page(tenant, job)
        # Simulate process loss after a committed page; a new lease resumes the frontier.
        async with tenant_tx(crawler.engine, tenant) as conn:
            await conn.execute(
                text(
                    "UPDATE crawl_jobs SET lease_until=clock_timestamp()-interval '1 second' WHERE tenant_id=:t AND id=:j"
                ),
                {"t": tenant, "j": first},
            )
        replacement = await crawler.lease(tenant)
        assert replacement is not None and replacement["fence"] != job["fence"]
        assert not await crawler.page(tenant, job)
        await crawler.run_job(tenant, replacement)
        listing = (await owner.get("/v1/crawls/jobs")).json()["items"]
        result = next(row for row in listing if row["id"] == str(first))
        assert (result["state"], result["items"], result["pages"], result["added"]) == ("COMPLETE", 4, 2, 4)
        exported = await owner.get(f"/v1/crawls/jobs/{first}/export")
        assert exported.status_code == 200
        assert len([json.loads(line) for line in exported.text.splitlines()]) == 4
        board.admin.patch("/admin/settings", json={"layout_variant": "b"}).raise_for_status()
        # Fixture destination caches adversity for one second.
        await asyncio.sleep(1.1)
        broken = await owner.post("/v1/crawls/jobs", json={"definition": "owned-catalogue"})
        broken_id = UUID(broken.json()["id"])
        broken_job = await crawler.lease(tenant)
        assert broken_job
        await crawler.run_job(tenant, broken_job)
        async with tenant_tx(crawler.engine, tenant) as conn:
            state = (
                await conn.execute(
                    text("SELECT state,alerts,removed FROM crawl_jobs WHERE tenant_id=:t AND id=:j"),
                    {"t": tenant, "j": broken_id},
                )
            ).one()
            assert state.state == "FAILED" and "zero_results" in state.alerts and state.removed == 0
            assert await conn.scalar(text("SELECT count(*) FROM crawl_items WHERE tenant_id=:t"), {"t": tenant}) == 4
            await conn.execute(
                text(
                    "UPDATE crawl_jobs SET completed_at=clock_timestamp()-interval '30 days' WHERE tenant_id=:t AND id=:j"
                ),
                {"t": tenant, "j": first},
            )
        await crawler.retention(tenant)
        assert (await owner.get(f"/v1/crawls/jobs/{first}/export")).status_code == 404
        assert not (tmp_path / str(tenant) / (str(first) + ".jsonl")).exists()


@pytest.mark.integration
async def test_crawl_cancellation_and_cross_tenant_isolation(
    api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    crawler = runner(api, tmp_path, monkeypatch)
    contract = definitions(api.cfg.config_dir).definitions["owned-catalogue"]
    async with tenant_tx(crawler.engine, api.tenant_id) as conn:
        key = await submit(conn, api.tenant_id, "owned-catalogue", contract, crawler.cfg.crawl.max_pages)
        await conn.execute(
            text("UPDATE crawl_jobs SET cancel_requested=true WHERE tenant_id=:t AND id=:j"),
            {"t": api.tenant_id, "j": key},
        )
    async with tenant_tx(crawler.engine, uuid4()) as conn:
        assert await conn.scalar(text("SELECT count(*) FROM crawl_jobs")) == 0
    job = await crawler.lease(api.tenant_id)
    assert job
    await crawler.run_job(api.tenant_id, job)
    async with tenant_tx(crawler.engine, api.tenant_id) as conn:
        assert (
            await conn.scalar(
                text("SELECT state FROM crawl_jobs WHERE tenant_id=:t AND id=:j"), {"t": api.tenant_id, "j": key}
            )
            == "CANCELLED"
        )
    async with api.client() as public:
        assert (await public.post("/v1/crawls/jobs", json={"definition": "owned-catalogue"})).status_code in (401, 403)
        assert (await public.get(f"/v1/crawls/jobs/{key}/export")).status_code == 403


def test_css_extraction_allowlist() -> None:
    contract = (
        definitions(Path(__file__).resolve().parents[3] / "config")
        .definitions["owned-catalogue"]
        .model_copy(
            update={
                "format": "html",
                "rows": "article",
                "links": "a.next",
                "identity_field": "ref",
                "required_fields": ["ref"],
                "fields": {"ref": FieldSpec(source=".ref", type="string", max_length=128)},
            }
        )
    )
    contract = type(contract).model_validate(contract.model_dump())
    items, links = extract(contract, b'<article><b class="ref">owned-1</b><p>private unlisted value</p></article>', 10)
    assert items == [{"ref": "owned-1"}] and links == []


def test_real_fetch_pins_owned_loopback_and_bounds_body(board: Board) -> None:
    board.admin.patch("/admin/settings", json={"layout_variant": "a"}).raise_for_status()
    time.sleep(1.1)
    response = fetch(
        board.url + "/catalogue.json", board.url, allow_private=True, timeout=2, limit=65536, user_agent="test"
    )
    assert response.status == 200 and "items" in json.loads(response.body)
    with pytest.raises(EgressDenied):
        fetch(board.url + "/catalogue.json", board.url, allow_private=True, timeout=2, limit=10, user_agent="test")


@pytest.mark.integration
async def test_crawl_listing_obeys_configured_default(api: Api, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(api.app.state.services.cfg.api, "page_size_default", 1)
    contract = definitions(api.cfg.config_dir).definitions["owned-catalogue"]
    async with tenant_tx(api.app.state.services.engine, api.tenant_id) as conn:
        for _ in range(2):
            key = await submit(conn, api.tenant_id, "page-" + uuid4().hex, contract, 100)
            await conn.execute(text("UPDATE crawl_jobs SET state='CANCELLED' WHERE id=:j"), {"j": key})
    async with api.client() as visitor:
        response = await visitor.get("/v1/crawls/jobs")
        assert response.status_code == 200 and len(response.json()["items"]) == 1
        assert len((await visitor.get("/v1/crawls/jobs?limit=2")).json()["items"]) == 2


@pytest.mark.integration
async def test_crawl_retention_is_bounded_by_configuration(
    api: Api, db: Db, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    crawler = runner(api, tmp_path, monkeypatch)
    crawler.cfg.crawl.retention_batch = 1
    tenant = await new_tenant(db)
    contract = definitions(api.cfg.config_dir).definitions["owned-catalogue"]
    paths = []
    async with tenant_tx(crawler.engine, tenant) as conn:
        for index in range(2):
            key = await submit(conn, tenant, "bounded-" + uuid4().hex, contract, 100)
            path = tmp_path / str(tenant) / (str(key) + ".jsonl")
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('{"ref":"test"}\n', encoding="utf-8")
            paths.append(path)
            await conn.execute(
                text(
                    "UPDATE crawl_jobs SET state='COMPLETE',artifact=:a, "
                    "completed_at=clock_timestamp()-make_interval(days=>:days) WHERE id=:j"
                ),
                {"a": path.name, "days": 31 - index, "j": key},
            )
    await crawler.retention(tenant)
    assert not paths[0].exists() and paths[1].exists()
    await crawler.retention(tenant)
    assert not paths[1].exists()
