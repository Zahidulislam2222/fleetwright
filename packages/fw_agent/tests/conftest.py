"""Agent tests need no Docker; opt in to the installed local-model proof explicitly."""

from __future__ import annotations

import asyncio
import socket
from collections.abc import AsyncIterator
from pathlib import Path
from typing import Any

import httpx
import pytest
import uvicorn
from fw_agent.app import create_app

from fw_core.settings import AgentAppSettings, AgentSettings

ROOT = Path(__file__).resolve().parents[3]


def pytest_addoption(parser: pytest.Parser) -> None:
    parser.addoption(
        "--agent-model-proof",
        action="store_true",
        default=False,
        help="exercise the configured installed Ollama model and real Chromium",
    )


@pytest.fixture
def agent_settings(tmp_path: Path) -> AgentAppSettings:
    with socket.socket() as listener:
        listener.bind(("127.0.0.1", 0))
        port = listener.getsockname()[1]
    return AgentAppSettings(
        environment="test",
        config_dir=ROOT / "config",
        agent=AgentSettings(
            database=tmp_path / "agent.sqlite",
            profile_directory=tmp_path / "profile",
            evidence_directory=tmp_path / "evidence",
            model_url="http://127.0.0.1:11434",
            model_id="qwen3:1.7b",
            host="127.0.0.1",
            port=port,
            allowed_origins=[f"http://127.0.0.1:{port}"],
        ),
    )


@pytest.fixture
async def agent_server(agent_settings: AgentAppSettings) -> AsyncIterator[tuple[Any, httpx.AsyncClient]]:
    app = create_app(agent_settings)
    server = uvicorn.Server(
        uvicorn.Config(
            app, host=agent_settings.agent.host, port=agent_settings.agent.port, log_level="warning", access_log=False
        )
    )
    task = asyncio.create_task(server.serve())
    while not server.started:
        if task.done():
            await task
        await asyncio.sleep(0.01)
    async with httpx.AsyncClient(base_url=agent_settings.agent.allowed_origins[0], trust_env=False) as client:
        await client.get("/")
        yield app, client
    server.should_exit = True
    await task


async def wait_state(
    client: httpx.AsyncClient, task_id: str, terminal: set[str], seconds: float = 30
) -> dict[str, Any]:
    async with asyncio.timeout(seconds):
        while True:
            response = await client.get(f"/api/tasks/{task_id}")
            response.raise_for_status()
            task: dict[str, Any] = response.json()
            if task["state"] in terminal:
                return task
            await asyncio.sleep(0.05)
