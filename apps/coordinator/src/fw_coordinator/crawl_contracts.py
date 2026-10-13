"""Validated crawl extraction contracts. Only operator-maintained definitions may select fields."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Literal

from bs4 import BeautifulSoup, Tag
from pydantic import BaseModel, ConfigDict, Field, model_validator

from fw_core.data import load_yaml


class FieldSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = Field(max_length=200)
    type: Literal["string", "integer"]
    attribute: str | None = None
    max_length: int = Field(default=4096, ge=1, le=4096)


class Definition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(max_length=100)
    origin: str = Field(pattern="^[a-z][a-z0-9_]{0,63}$")
    seeds: list[str] = Field(min_length=1, max_length=20)
    format: Literal["json", "html"]
    rows: str = Field(max_length=200)
    links: str | None = None
    identity_field: str
    personal_data: bool
    fields: dict[str, FieldSpec] = Field(min_length=1, max_length=30)
    required_fields: list[str]
    respect_robots: bool = True

    @model_validator(mode="after")
    def valid_definition(self) -> Definition:
        if self.identity_field not in self.fields or not set(self.required_fields) <= self.fields.keys():
            raise ValueError("identity and required fields must be allowed extraction fields")
        identity = self.fields[self.identity_field]
        if identity.type == "string" and identity.max_length > 256:
            raise ValueError("indexed identity fields must have an explicit length at most 256")
        if any(not path.startswith("/") or path.startswith("//") for path in self.seeds):
            raise ValueError("seeds must be absolute same-origin paths")
        return self

    def fingerprint(self) -> str:
        return hashlib.sha256(json.dumps(self.model_dump(), sort_keys=True, separators=(",", ":")).encode()).hexdigest()


class Contracts(BaseModel):
    model_config = ConfigDict(extra="forbid")
    version: Literal[1]
    definitions: dict[str, Definition]


def definitions(config: Path) -> Contracts:
    return load_yaml(config, "crawls.yaml", Contracts)


def pointer(value: Any, path: str) -> Any:
    if path == "":
        return value
    if not path.startswith("/"):
        raise ValueError("JSON pointer must start with slash")
    for raw in path[1:].split("/"):
        part = raw.replace("~1", "/").replace("~0", "~")
        value = value[int(part)] if isinstance(value, list) else value[part]
    return value


def extract(contract: Definition, body: bytes, max_items: int) -> tuple[list[dict[str, str | int]], list[str]]:
    if contract.format == "json":
        document = json.loads(body)
        rows = pointer(document, contract.rows)
        links = pointer(document, contract.links) if contract.links else []
    else:
        document = BeautifulSoup(body, "html.parser")
        rows = document.select(contract.rows, limit=max_items + 1)
        links = [str(tag.get("href")) for tag in document.select(contract.links)] if contract.links else []
    if not isinstance(rows, list) or len(rows) > max_items or not isinstance(links, list) or len(links) > max_items:
        raise ValueError("extraction shape or count limit")
    result = []
    for row in rows:
        item: dict[str, str | int] = {}
        for key, spec in contract.fields.items():
            if isinstance(row, Tag):
                node = row.select_one(spec.source)
                value = (
                    node.get(spec.attribute) if node and spec.attribute else node.get_text(strip=True) if node else None
                )
            else:
                try:
                    value = pointer(row, spec.source)
                except (KeyError, IndexError):
                    if key in contract.required_fields:
                        raise
                    continue
            if value is None or isinstance(value, (dict, list, bool)):
                raise ValueError("invalid extraction field")
            if spec.type == "integer":
                if not isinstance(value, int) and not (isinstance(value, str) and re.fullmatch(r"-?\d{1,18}", value)):
                    raise ValueError("integer extraction field has invalid type")
                item[key] = int(value)
            else:
                rendered = str(value)
                if len(rendered) > spec.max_length:
                    raise ValueError("extraction field length exceeded")
                item[key] = rendered
        if not item.get(contract.identity_field) or not all(key in item for key in contract.required_fields):
            raise ValueError("missing required extraction field")
        result.append(item)
    if any(not isinstance(link, str) or not link.startswith("/") or link.startswith("//") for link in links):
        raise ValueError("extracted links must be same-origin paths")
    return result, links
