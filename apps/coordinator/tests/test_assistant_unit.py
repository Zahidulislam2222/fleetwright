"""Help-assistant parts that need no database or API: the knowledge index, text cleaning, prompt
fitting, and the documentation fallback when Redis is down (global Rule 24)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import httpx
import pytest
from pydantic import SecretStr
from redis.asyncio import Redis

from fw_coordinator.assistant import Assistant, AssistantCopy, clean
from fw_coordinator.assistant_knowledge import KNOWLEDGE_FILE, Knowledge, build
from fw_core.data import load_yaml
from fw_core.settings import AssistantSettings

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config"


def expect(condition: object, message: str = "expectation failed") -> None:
    """Explicit test failure (keeps optimised-away `assert` out of security scans)."""
    if not condition:
        pytest.fail(message)


def settings(**overrides: Any) -> AssistantSettings:
    values: dict[str, Any] = {
        "enabled": True,
        "provider_url": "https://provider.example.test/v1/chat/completions",
        "api_key": SecretStr("fake-key-for-tests"),
        "model_id": "fake/model",
        "price_input_per_mtok_usd": 0.10,
        "price_output_per_mtok_usd": 0.50,
    }
    return AssistantSettings(**(values | overrides))


def assistant(redis: Redis, **overrides: Any) -> Assistant:
    copy = load_yaml(CONFIG, "assistant.yaml", AssistantCopy)
    never = httpx.AsyncClient(transport=httpx.MockTransport(lambda _: pytest.fail("no provider call expected")))
    return Assistant(settings(**overrides), copy, Knowledge.load(CONFIG), redis, never)


def test_the_knowledge_index_matches_the_published_documents() -> None:
    copy = load_yaml(CONFIG, "assistant.yaml", AssistantCopy)
    stored = json.loads((CONFIG / KNOWLEDGE_FILE).read_text(encoding="utf-8"))
    rebuilt = build(ROOT, copy.knowledge_sources, copy.version)
    expect(stored == rebuilt, "run: uv run python tools/dev/build_assistant_knowledge.py")


def test_the_index_digest_ignores_line_endings(tmp_path: Path) -> None:
    lf = "# Title" + chr(10) + chr(10) + "Body text." + chr(10)
    (tmp_path / "a.md").write_bytes(lf.encode())
    (tmp_path / "b.md").write_bytes(lf.replace(chr(10), chr(13) + chr(10)).encode())
    built = build(tmp_path, ["a.md", "b.md"], "v")
    expect(built["sources"]["a.md"] == built["sources"]["b.md"])


def test_retrieval_finds_the_section_that_answers_the_question() -> None:
    knowledge = Knowledge.load(CONFIG)
    found = knowledge.search("why is a claim UNKNOWN and is it retried", 4)
    expect(found and any("UNKNOWN" in s.text for s in found))
    expect(knowledge.search("the of and", 4) == [])


def test_cleaning_removes_invisible_and_bidirectional_characters() -> None:
    sneaky = "safe" + chr(0x202E) + "text" + chr(0x200B) + " with" + chr(0) + " control" + chr(10) + "line"
    expect(clean(sneaky, 100) == "safetext with control" + chr(10) + "line")


def test_settings_refuse_a_call_timeout_longer_than_the_deadline() -> None:
    with pytest.raises(ValueError, match="deadline"):
        settings(timeout_s=30, total_deadline_s=25)
    with pytest.raises(ValueError):
        AssistantSettings(enabled=True, api_key=SecretStr(" "))


def test_fitting_drops_old_history_but_never_the_question() -> None:
    a = assistant(Redis.from_url("redis://localhost:1/0"), max_prompt_chars=2000)
    head = [{"role": "system", "content": "rules"}]
    earlier = [{"role": "user", "content": "old " * 200}, {"role": "assistant", "content": "older " * 200}]
    turn = [{"role": "user", "content": "the current question"}]
    fitted = a._fit(head, earlier, turn)
    expect(fitted[-1]["content"] == "the current question", str(fitted))
    expect(len(json.dumps(fitted)) <= 2000)


async def test_a_redis_outage_still_answers_from_the_documentation() -> None:
    down = Redis.from_url("redis://localhost:1/0", socket_connect_timeout=0.2, socket_timeout=0.2)
    a = assistant(down)

    async def no_tools(name: str, args: dict[str, Any]) -> Any:
        pytest.fail(f"no tool expected, got {name} {args}")

    try:
        body = await a.ask("ip:test", False, "What happens to an UNKNOWN claim?", [], no_tools)
        voted = await a.feedback("abcdefghijkl", True)
    finally:
        await down.aclose()
    expect(body["mode"] == "search" and body["reason"] == "search_only" and body["sources"], str(body))
    expect(body["ai_generated"] is False and voted is False)


def test_settings_refuse_a_zero_price_and_a_deadline_beyond_the_proxy_timeout() -> None:
    with pytest.raises(ValueError):
        settings(price_input_per_mtok_usd=0)
    with pytest.raises(ValueError):
        settings(total_deadline_s=29, timeout_s=20)
