"""Board test kit: runs a real mock board process (uvicorn) against the local Compose stack.
The fixtures are re-exported by conftest.py; tests import the Board type from here."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import httpx
import pytest
from pydantic_settings import SettingsConfigDict

from fw_core.settings import BoardSettings, MailpitSettings, _Base

ROOT = Path(__file__).resolve().parents[3]
STARTUP_S = 30


class BoardTestSettings(_Base):
    model_config = SettingsConfigDict(
        env_prefix="FW_", env_nested_delimiter="__", extra="ignore", env_file=ROOT / ".env"
    )
    board: BoardSettings
    mailpit: MailpitSettings


@dataclass
class Board:
    url: str
    admin: httpx.Client
    settings: BoardTestSettings


def _free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return int(s.getsockname()[1])


@pytest.fixture(scope="session")
def board() -> Iterator[Board]:
    cfg = BoardTestSettings()  # type: ignore[call-arg]
    port = _free_port()
    url = f"http://127.0.0.1:{port}"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "--factory",
            "mockboard.app:create_app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=ROOT,
        env={**os.environ, "FW_ENVIRONMENT": "test"},
        stdout=subprocess.DEVNULL,
        stderr=subprocess.STDOUT,
    )
    try:
        deadline = time.monotonic() + STARTUP_S
        while True:
            try:
                if httpx.get(f"{url}/healthz", timeout=1).status_code == 200:
                    break
            except httpx.HTTPError:
                pass
            if time.monotonic() > deadline or proc.poll() is not None:
                raise RuntimeError("mock board did not start")
            time.sleep(0.3)
        admin = httpx.Client(
            base_url=url, headers={"Authorization": f"Bearer {cfg.board.admin_token.get_secret_value()}"}, timeout=10
        )
        admin.post("/admin/reset").raise_for_status()
        yield Board(url, admin, cfg)
        admin.close()
    finally:
        proc.terminate()
        proc.wait(timeout=10)


@pytest.fixture(autouse=True)
def default_rules(board: Board) -> Iterator[None]:
    """Every test starts and ends with all adversity off and a fast feed."""
    calm = {
        "feed_rate_per_min": 600,
        "rate_limit_per_min": 0,
        "error_rate": 0,
        "slow_rate": 0,
        "slow_ms": 0,
        "ack_loss_rate": 0,
        "layout_variant": "a",
        "competitor_share": 0,
        "captcha_enabled": True,
        "captcha_after_requests": 600,
        "single_session": False,
    }
    board.admin.patch("/admin/settings", json=calm).raise_for_status()
    time.sleep(1.1)  # the board caches rules for up to 1 s
    yield
    board.admin.patch("/admin/settings", json=calm).raise_for_status()
