"""Real transport and durable-worker regressions for independent review findings."""

from __future__ import annotations

import asyncio
import json
import socket
import ssl
import threading
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from datetime import UTC, datetime, timedelta
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from itertools import pairwise
from pathlib import Path
from uuid import uuid4

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from sqlalchemy import text
from test_crawler import runner

from apikit import Api
from fw_coordinator.crawl_contracts import definitions
from fw_coordinator.crawl_http import EgressDenied, addresses, fetch
from fw_coordinator.crawls import submit
from fw_core.db import tenant_tx


@contextmanager
def server(
    action: Callable[[BaseHTTPRequestHandler], None], tls: ssl.SSLContext | None = None
) -> Iterator[ThreadingHTTPServer]:
    class Handler(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            action(self)

        def log_message(self, *_args: object) -> None:
            pass

    http = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    if tls:
        http.socket = tls.wrap_socket(http.socket, server_side=True)
    thread = threading.Thread(target=http.serve_forever, daemon=True)
    thread.start()
    try:
        yield http
    finally:
        http.shutdown()
        http.server_close()
        thread.join(timeout=3)


def reply(handler: BaseHTTPRequestHandler, body: bytes, status: int = 200) -> None:
    handler.send_response(status)
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def test_mixed_dns_answers_fail_closed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo", lambda *_a, **_k: [(0, 0, 0, "", ("8.8.8.8", 80)), (0, 0, 0, "", ("127.0.0.1", 80))]
    )
    with pytest.raises(EgressDenied):
        addresses("owned.test", 80, False)


def test_redirect_to_metadata_is_never_followed() -> None:
    paths = []

    def redirect(handler: BaseHTTPRequestHandler) -> None:
        paths.append(handler.path)
        handler.send_response(302)
        handler.send_header("Location", "http://169.254.169.254/latest/meta-data")
        handler.end_headers()

    with server(redirect) as http:
        origin = f"http://127.0.0.1:{http.server_port}"
        with pytest.raises(EgressDenied):
            fetch(origin + "/redirect", origin, allow_private=True, timeout=1, limit=1024, user_agent="test")
    assert paths == ["/redirect"]


def test_real_tls_sni_trust_hostname_and_single_dns_lookup(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "owned.test")])
    certificate = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(datetime.now(UTC) - timedelta(minutes=1))
        .not_valid_after(datetime.now(UTC) + timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("owned.test")]), critical=False)
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(key, hashes.SHA256())
    )
    cert_file, key_file = tmp_path / "test-cert.pem", tmp_path / "test-key.pem"
    cert_file.write_bytes(certificate.public_bytes(serialization.Encoding.PEM))
    key_file.write_bytes(
        key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption())
    )
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    context.load_cert_chain(cert_file, key_file)
    original_context, original_dns = ssl.create_default_context, socket.getaddrinfo
    lookups = []

    def dns(host: str, port: int, *args: object, **kwargs: object):
        if host in {"owned.test", "wrong.test"}:
            lookups.append(host)
            return original_dns("127.0.0.1", port, *args, **kwargs)
        return original_dns(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", dns)
    monkeypatch.setattr(ssl, "create_default_context", lambda: original_context(cafile=str(cert_file)))
    with server(lambda handler: reply(handler, b"owned"), context) as http:
        origin = f"https://owned.test:{http.server_port}"
        assert fetch(origin, origin, allow_private=True, timeout=2, limit=1024, user_agent="test").body == b"owned"
        assert lookups == ["owned.test"]
        wrong = f"https://wrong.test:{http.server_port}"
        with pytest.raises(ssl.SSLCertVerificationError):
            fetch(wrong, wrong, allow_private=True, timeout=2, limit=1024, user_agent="test")


@pytest.mark.integration
@pytest.mark.parametrize("failure", ["pointer", "truncated"])
async def test_malformed_page_retries_to_failed_and_next_job_survives(
    api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, failure: str
) -> None:
    crawler = runner(api, tmp_path, monkeypatch)
    base = definitions(api.cfg.config_dir).definitions["owned-catalogue"]
    contract = base.model_copy(update={"rows": "/items/99"}) if failure == "pointer" else base
    broken = [True]

    def destination(handler: BaseHTTPRequestHandler) -> None:
        if handler.path == "/robots.txt":
            reply(handler, b"User-agent: *\nAllow: /\n")
        elif broken[0] and failure == "truncated":
            handler.send_response(200)
            handler.send_header("Content-Length", "1000")
            handler.end_headers()
            handler.wfile.write(b'{"items":[],"next":[]}')
            handler.close_connection = True
        elif broken[0]:
            reply(handler, b'{"items":[],"next":[]}')
        else:
            reply(
                handler,
                b'{"items":[{"ref":"next","origin":"a","destination":"b","equipment":"Van","rate_usd":1}],"next":[]}',
            )

    with server(destination) as http:
        crawler.cfg.board_client = crawler.cfg.board_client.model_copy(
            update={"internal_url": f"http://127.0.0.1:{http.server_port}"}
        )
        async with tenant_tx(crawler.engine, api.tenant_id) as conn:
            key = await submit(conn, api.tenant_id, "adversity-" + uuid4().hex, contract, 100)
        job = await crawler.lease(api.tenant_id)
        assert job and job["id"] == key
        await crawler.run_job(api.tenant_id, job)
        async with tenant_tx(crawler.engine, api.tenant_id) as conn:
            state = (
                await conn.execute(
                    text("SELECT state,errors FROM crawl_jobs WHERE tenant_id=:t AND id=:j"),
                    {"t": api.tenant_id, "j": key},
                )
            ).one()
            assert state.state == "FAILED" and state.errors == crawler.cfg.crawl.max_attempts
        # Failure must release the Python control flow for a subsequent successful cycle.
        broken[0] = False
        async with tenant_tx(crawler.engine, api.tenant_id) as conn:
            followup = await submit(conn, api.tenant_id, "followup-" + uuid4().hex, base, 100)
        next_job = await crawler.lease(api.tenant_id)
        assert next_job and next_job["id"] == followup
        await crawler.run_job(api.tenant_id, next_job)
        async with tenant_tx(crawler.engine, api.tenant_id) as conn:
            assert (
                await conn.scalar(
                    text("SELECT state FROM crawl_jobs WHERE tenant_id=:t AND id=:j"),
                    {"t": api.tenant_id, "j": followup},
                )
                == "COMPLETE"
            )


@pytest.mark.integration
async def test_slow_drip_fetch_is_physically_terminated(
    api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    crawler = runner(api, tmp_path, monkeypatch)
    crawler.cfg.crawl = crawler.cfg.crawl.model_copy(update={"request_budget_s": 2, "timeout_s": 0.2})
    connected, disconnected = threading.Event(), threading.Event()

    def drip(handler: BaseHTTPRequestHandler) -> None:
        handler.send_response(200)
        handler.send_header("Content-Length", "200")
        handler.end_headers()
        connected.set()
        try:
            for _ in range(200):
                handler.wfile.write(b"x")
                handler.wfile.flush()
                time.sleep(0.05)
        except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
            disconnected.set()

    with server(drip) as http:
        crawler.cfg.board_client = crawler.cfg.board_client.model_copy(
            update={"internal_url": f"http://127.0.0.1:{http.server_port}"}
        )
        started = time.monotonic()
        task = asyncio.create_task(crawler.request("/slow", "owned_board"))
        assert await asyncio.to_thread(connected.wait, 2)
        with pytest.raises(TimeoutError):
            await task
        assert time.monotonic() - started < 3
        assert await asyncio.to_thread(disconnected.wait, 2)


@pytest.mark.integration
async def test_each_request_is_paced_and_backlink_at_limit_is_not_truncation(
    api: Api, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    crawler = runner(api, tmp_path, monkeypatch)
    crawler.cfg.crawl = crawler.cfg.crawl.model_copy(update={"domain_delay_s": 1, "max_pages": 2})
    timestamps = []

    def destination(handler: BaseHTTPRequestHandler) -> None:
        timestamps.append(time.monotonic())
        if handler.path == "/robots.txt":
            reply(handler, b"User-agent: *\nAllow: /\n")
            return
        ref = "one" if handler.path == "/catalogue.json" else "two"
        next_page = "/page-two" if ref == "one" else "/catalogue.json"
        reply(
            handler,
            json.dumps(
                {
                    "items": [
                        {"ref": ref, "origin": "owned", "destination": "owned", "equipment": "Van", "rate_usd": 1}
                    ],
                    "next": [next_page],
                }
            ).encode(),
        )

    with server(destination) as http:
        crawler.cfg.board_client = crawler.cfg.board_client.model_copy(
            update={"internal_url": f"http://127.0.0.1:{http.server_port}"}
        )
        contract = definitions(api.cfg.config_dir).definitions["owned-catalogue"]
        async with tenant_tx(crawler.engine, api.tenant_id) as conn:
            with pytest.raises(ValueError):
                await submit(
                    conn, api.tenant_id, "over-budget", contract.model_copy(update={"seeds": ["/one", "/two"]}), 1
                )
            key = await submit(conn, api.tenant_id, "backlink-" + uuid4().hex, contract, 2)
        job = await crawler.lease(api.tenant_id)
        assert job
        await crawler.run_job(api.tenant_id, job)
        assert len(timestamps) == 3
        assert all(b - a >= 0.9 for a, b in pairwise(timestamps))
        async with tenant_tx(crawler.engine, api.tenant_id) as conn:
            state = (
                await conn.execute(
                    text("SELECT state,pages,alerts FROM crawl_jobs WHERE tenant_id=:t AND id=:j"),
                    {"t": api.tenant_id, "j": key},
                )
            ).one()
            assert state.state == "COMPLETE" and state.pages == 2 and "page_limit" not in state.alerts
