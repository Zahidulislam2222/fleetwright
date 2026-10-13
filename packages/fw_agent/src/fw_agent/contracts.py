"""Immutable wire syntax and typed maintained task data; no model-controlled actions."""

from __future__ import annotations

import hashlib
import ipaddress
import json
from pathlib import Path
from typing import Any, Literal
from urllib.parse import urlsplit

import yaml
from pydantic import BaseModel, ConfigDict, Field, field_validator

CSRF_HEADER = "X-CSRF-Token"
SESSION_COOKIE = "fw_local_agent"
OLLAMA_CHAT_PATH = "/api/chat"
OLLAMA_SHOW_PATH = "/api/show"
OLLAMA_TAGS_PATH = "/api/tags"
# Adapter invariant: two prepare navigations, two execute navigations, four fills, one click.
TEMPLATE_ACTION_COST = 9


def origin(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname or parsed.username or parsed.password:
        raise ValueError("an explicit HTTP(S) origin is required")
    if parsed.fragment:
        raise ValueError("URL fragments are not allowed")
    host = parsed.hostname.lower()
    if ":" in host:
        host = f"[{host}]"
    port = parsed.port
    standard = 80 if parsed.scheme == "http" else 443
    return f"{parsed.scheme}://{host}" + (f":{port}" if port and port != standard else "")


def loopback_url(url: str) -> None:
    parsed = urlsplit(url)
    origin(url)
    host = parsed.hostname or ""
    if not ipaddress.ip_address(host).is_loopback:
        raise ValueError("the model/CDP endpoint must be loopback; cloud inference is disabled")


def fingerprint(value: dict[str, Any]) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    ).hexdigest()


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Draft(StrictModel):
    title: str = Field(min_length=1, max_length=200)
    body: str = Field(min_length=1, max_length=8000)


class Template(StrictModel):
    id: str = Field(pattern="^[a-z][a-z0-9_]{0,40}$")
    name: str
    description: str
    prompt: str
    source_path: str
    form_path: str
    accept_path: str
    receipt_path: str
    source_selector: str
    title_selector: str
    body_selector: str
    submit_selector: str
    task_selector: str
    hash_selector: str
    receipt_selector: str
    lab_source: str
    action: Literal["save_owned_record"]

    @field_validator("source_path", "form_path", "accept_path", "receipt_path")
    @classmethod
    def relative_path(cls, value: str) -> str:
        if not value.startswith("/") or value.startswith("//") or "?" in value or "#" in value or "\\" in value:
            raise ValueError("template paths must be origin-relative paths")
        return value


class AgentData(StrictModel):
    title: str
    subtitle: str
    safety_notice: str
    poll_interval_ms: int = Field(ge=100, le=60000)
    model_system_prompt: str
    ui: dict[str, str]
    templates: list[Template] = Field(min_length=3, max_length=20)

    def template(self, template_id: str) -> Template:
        for item in self.templates:
            if item.id == template_id:
                return item
        raise ValueError("unknown template")


def load_data(directory: Path) -> AgentData:
    data = AgentData.model_validate(yaml.safe_load((directory / "agent.yaml").read_text(encoding="utf-8")))
    if len({t.id for t in data.templates}) != len(data.templates):
        raise ValueError("template identifiers must be unique")
    return data
