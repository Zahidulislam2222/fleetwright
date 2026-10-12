"""Versioned contracts for authorized workflows, independent of freight detection/filtering."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_validator

from fw_core.data import load_yaml


def digest(value: Any) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode()
    ).hexdigest()


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    max_length: int = Field(ge=1, le=1000)
    pattern: str | None = None
    choices: frozenset[str] | None = None

    @field_serializer("choices")
    def canonical_choices(self, choices: frozenset[str] | None) -> list[str] | None:
        return sorted(choices) if choices is not None else None


class WorkflowSpec(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    revision: int = Field(ge=1)
    target: str
    adapter: Literal["freight", "service_request"]
    description: str
    fields: dict[str, FieldSpec]
    page: str
    action_selector: str
    action_path: str
    input_selectors: dict[str, str]
    receipt_path: str
    receipt_collection: str
    receipt_key: str
    success_statuses: frozenset[int]
    failure_statuses: frozenset[int]
    authoritative_absence: bool

    @field_serializer("success_statuses", "failure_statuses")
    def canonical_statuses(self, statuses: frozenset[int]) -> list[int]:
        return sorted(statuses)

    @model_validator(mode="after")
    def safe_paths(self) -> WorkflowSpec:
        for path in (self.page, self.receipt_path, self.action_path):
            if not path.startswith("/") or path.startswith("//") or "\\" in path or ".." in path:
                raise ValueError("workflow paths must remain on the configured owned origin")
        if self.success_statuses & self.failure_statuses:
            raise ValueError("success and failure statuses must be disjoint")
        return self

    def validate_inputs(self, inputs: dict[str, str]) -> dict[str, str]:
        if inputs.keys() != self.fields.keys():
            raise ValueError("inputs must match the workflow contract exactly")
        for key, value in inputs.items():
            field = self.fields[key]
            if not value.strip() or len(value) > field.max_length:
                raise ValueError(f"invalid length for {key}")
            if field.pattern and re.fullmatch(field.pattern, value) is None:
                raise ValueError(f"invalid format for {key}")
            if field.choices is not None and value not in field.choices:
                raise ValueError(f"invalid choice for {key}")
        return dict(inputs)

    @property
    def fingerprint(self) -> str:
        return digest(self.model_dump(mode="json"))


class OperatorMessages(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    unknown_outcome: str
    queued_stalled: str


class Workflows(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    server_name: str
    instructions: str
    operator_messages: OperatorMessages
    workflows: dict[str, WorkflowSpec]

    def get(self, name: str) -> WorkflowSpec:
        if name not in self.workflows:
            raise ValueError("unsupported workflow")
        return self.workflows[name]


def load_workflows(config_dir: Path) -> Workflows:
    return load_yaml(config_dir, "workflows.yaml", Workflows)
