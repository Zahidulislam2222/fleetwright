"""Test kit for the `/v1` API: a seeded demo tenant with one user per role, and signed-in clients.

Each test session uses its own tenant slug and user emails, and every client sends its own
forwarded address, so lockout counters never leak between tests or runs."""

from __future__ import annotations

import base64
import secrets
from collections.abc import AsyncIterator
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
import pyotp
import pytest
from fastapi import FastAPI
from pydantic import SecretStr
from pydantic_settings import SettingsConfigDict

from boardkit import Board
from fw_coordinator import seed as seeding
from fw_coordinator.api import create_app
from fw_coordinator.demo import load_demo
from fw_core.crypto import Envelope
from fw_core.db import make_engine
from fw_core.settings import CoordinatorSettings, SeedAppSettings, SeedSettings

ROOT = Path(__file__).resolve().parents[3]
PASSWORD = "test-password-not-secret"


class ApiTestSettings(CoordinatorSettings):
    model_config = SettingsConfigDict(
        env_prefix="FW_", env_nested_delimiter="__", extra="ignore", env_file=ROOT / ".env"
    )


def random_ip() -> str:
    return f"10.{secrets.randbelow(250)}.{secrets.randbelow(250)}.{secrets.randbelow(250) + 1}"


def b32() -> str:
    return base64.b32encode(secrets.token_bytes(20)).decode()


@dataclass
class User:
    email: str
    role: str
    totp: str  # base32


@dataclass
class Api:
    app: FastAPI
    cfg: CoordinatorSettings
    tenant_id: UUID
    users: dict[str, User]

    def client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            transport=httpx.ASGITransport(app=self.app),
            base_url="http://api.test",
            headers={"X-Forwarded-For": random_ip()},
        )

    async def signed_in(self, role: str) -> httpx.AsyncClient:
        user = self.users[role]
        c = self.client()
        r = await c.post("/v1/auth/login", json={"email": user.email, "password": PASSWORD})
        assert r.status_code == 200, r.text
        r = await c.post("/v1/auth/mfa", json={"code": pyotp.TOTP(user.totp).now()})
        assert r.status_code == 200, r.text
        c.headers[self.cfg.auth.csrf_header] = r.json()["csrf"]
        return c


def settings(board: Board, slug: str, demo_password: str) -> CoordinatorSettings:
    base = ApiTestSettings()  # type: ignore[call-arg]
    return base.model_copy(
        update={
            "board_client": base.board_client.model_copy(update={"internal_url": board.url}),
            "auth": base.auth.model_copy(update={"cookie_secure": False}),
            "api": base.api.model_copy(update={"trusted_proxy_hops": 1}),
            "demo": base.demo.model_copy(
                update={
                    "tenant_slug": slug,
                    "public_read": True,
                    "show_demo_mfa_code": True,
                    "account_email": f"demo-{slug}@example.test",
                    "account_password": SecretStr(demo_password),
                    "reset_after_s": 60,
                }
            ),
        }
    )


@pytest.fixture(scope="session")
async def api(board: Board) -> AsyncIterator[Api]:
    slug = f"demo-{secrets.token_hex(4)}"
    cfg = settings(board, slug, PASSWORD)
    data = load_demo(ROOT / "config")
    owner = User(f"owner-{slug}@example.test", "owner", b32())
    seed_cfg = SeedAppSettings(
        environment="test",
        config_dir=ROOT / "config",
        app_db=cfg.app_db,
        vault=cfg.vault,
        board_client=cfg.board_client,
        demo=cfg.demo,
        seed=SeedSettings(
            cell="cell-a",
            owner_email=owner.email,
            owner_password=SecretStr(PASSWORD),
            owner_totp_b32=SecretStr(owner.totp),
        ),
    )
    result = await seeding.seed(seed_cfg, data)
    tenant_id = UUID(str(result["tenant"]))
    users = {"owner": owner}
    engine = make_engine(cfg.app_db.dsn, cfg.app_db, "test-api-users")
    envelope = Envelope(cfg.vault.master_key_b64.get_secret_value(), cfg.vault.key_id)
    for role in ("operator", "viewer", "replay", "lockout", "signout"):
        user = User(
            f"{role}-{slug}@example.test", "viewer" if role in ("replay", "lockout", "signout") else role, b32()
        )
        await seeding._user(engine, envelope, tenant_id, user.email, role.title(), user.role, PASSWORD, user.totp)
        users[role] = user
    await engine.dispose()
    app = create_app(cfg, data)
    async with app.router.lifespan_context(app):
        svc = app.state.services
        demo_code = await svc.auth.current_code(cfg.demo.account_email)
        assert demo_code is not None
        yield Api(app, cfg, tenant_id, users)


async def demo_client(api: Api) -> httpx.AsyncClient:
    """Signs in the shared demo login exactly as a visitor would: from the public hint."""
    c = api.client()
    hint = (await c.get("/v1/auth/demo-hint")).json()
    r = await c.post("/v1/auth/login", json={"email": hint["email"], "password": hint["password"]})
    assert r.status_code == 200, r.text
    r = await c.post("/v1/auth/mfa", json={"code": hint["code"]})
    assert r.status_code == 200, r.text
    c.headers[api.cfg.auth.csrf_header] = r.json()["csrf"]
    return c


def items(reply: httpx.Response) -> list[dict[str, Any]]:
    assert reply.status_code == 200, reply.text
    return list(reply.json()["items"])
