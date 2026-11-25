"""Paid, opt-in evaluation of the help assistant against the real model provider (global Rule 24).

Skipped unless FW_ASSISTANT_LIVE_EVAL=1 and FW_ASSISTANT_EVAL_KEY_FILE names the provider key file:
each run makes real, billed model calls, so it needs explicit cost approval. Provider, model and
prices come from the deployment settings (.env); only the key is read from the file, never printed.
Results (no key, no prompts) are written to var/verification/assistant-eval-<UTC time>.json."""

from __future__ import annotations

import json
import os
import re
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import httpx
import pytest
import yaml
from pydantic import SecretStr

from apikit import Api
from fw_coordinator.assistant import Assistant

pytestmark = pytest.mark.integration
ROOT = Path(__file__).resolve().parents[3]
EVAL = ROOT / "config" / "assistant-eval.yaml"


def expect(condition: object, message: str = "expectation failed") -> None:
    if not condition:
        pytest.fail(message)


def _check(case: dict[str, Any], body: dict[str, Any]) -> list[str]:
    text = body["answer"].lower()
    problems = []
    if body["mode"] != "ai":
        problems.append(f"not an AI answer ({body['reason']})")
    if case.get("any") and not any(w.lower() in text for w in case["any"]):
        problems.append(f"none of {case['any']}")
    for word in case.get("all", []):
        if word.lower() not in text:
            problems.append(f"missing {word}")
    for word in case.get("none", []):
        if word.lower() in text:
            problems.append(f"contains {word}")
    for pattern in case.get("none_regex", []):
        if re.search(pattern, body["answer"]):
            problems.append(f"matches {pattern}")
    if case.get("tools_any") and not set(case["tools_any"]) & set(body["used_tools"]):
        problems.append(f"no tool from {case['tools_any']}")
    return problems


@pytest.mark.skipif(os.environ.get("FW_ASSISTANT_LIVE_EVAL") != "1", reason="paid evaluation is opt-in")
async def test_live_assistant_meets_its_evaluation_thresholds(api: Api) -> None:
    key_file = Path(os.environ["FW_ASSISTANT_EVAL_KEY_FILE"])
    spec = yaml.safe_load(EVAL.read_text(encoding="utf-8"))
    limits = spec["thresholds"]
    svc = api.app.state.services
    original = svc.assistant
    cfg = api.cfg.assistant.model_copy(
        update={
            "enabled": True,
            "api_key": SecretStr(key_file.read_text(encoding="utf-8").strip()),
            "daily_budget_usd": limits["max_total_cost_usd"],
            "public_per_hour": 1000,
        }
    )
    expect(cfg.provider_url and cfg.model_id, "set FW_ASSISTANT__PROVIDER_URL and FW_ASSISTANT__MODEL_ID in .env")
    redis = svc.redis
    async for k in redis.scan_iter(match="fw:assistant:spend:*"):
        await redis.delete(k)
    results: list[dict[str, Any]] = []
    async with httpx.AsyncClient(timeout=cfg.timeout_s) as http:
        svc.assistant = Assistant(cfg, original.copy, original.knowledge, redis, http)
        try:
            async with api.client() as anon:
                for case in spec["cases"]:
                    before = await svc.assistant.stats()
                    started = time.monotonic()
                    r = await anon.post("/v1/assistant/ask", json={"question": case["question"]})
                    elapsed = time.monotonic() - started
                    after = await svc.assistant.stats()
                    body = r.json()
                    cost = (after.get("cost_micro", 0) - before.get("cost_micro", 0)) / 1_000_000
                    problems = _check(case, body) if r.status_code == 200 else [f"HTTP {r.status_code}"]
                    results.append(
                        {
                            "id": case["id"],
                            "passed": not problems,
                            "problems": problems,
                            "mode": body.get("mode"),
                            "tools": body.get("used_tools"),
                            "latency_s": round(elapsed, 2),
                            "cost_usd": round(cost, 6),
                            "answer": body.get("answer", "")[:1200],
                        }
                    )
        finally:
            svc.assistant = original
    latencies = sorted(r["latency_s"] for r in results)
    p95 = latencies[min(len(latencies) - 1, int(0.95 * len(latencies)))]
    summary = {
        "at": datetime.now(UTC).isoformat(),
        "model": cfg.model_id,
        "cases": len(results),
        "passed": sum(r["passed"] for r in results),
        "pass_rate": round(sum(r["passed"] for r in results) / len(results), 3),
        "p95_latency_s": p95,
        "total_cost_usd": round(sum(r["cost_usd"] for r in results), 6),
        "max_cost_usd": max(r["cost_usd"] for r in results),
        "results": results,
    }
    out = ROOT / "var" / "verification"
    out.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    (out / f"assistant-eval-{stamp}.json").write_text(json.dumps(summary, indent=1), encoding="utf-8")
    failed_required = [r["id"] for r in results if r["id"] in limits["must_pass"] and not r["passed"]]
    expect(not failed_required, f"required cases failed: {failed_required}")
    expect(summary["pass_rate"] >= limits["pass_rate"], f"pass rate {summary['pass_rate']}")
    expect(p95 <= limits["p95_latency_s"], f"p95 latency {p95}s")
    expect(summary["max_cost_usd"] <= limits["max_cost_usd_per_question"], f"max cost {summary['max_cost_usd']}")
