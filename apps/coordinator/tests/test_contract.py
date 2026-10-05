"""The wire contract stays in one piece: contracts/openapi.yaml is what the models generate, and the
console's TypeScript types have the same objects, the same fields and the same nullability."""

from __future__ import annotations

import re
import types
from pathlib import Path
from typing import Any, Union, get_args, get_origin

from apikit import ApiTestSettings
from fw_coordinator import schemas
from fw_coordinator.api import create_app
from fw_coordinator.contract import CONTRACT, render
from fw_queue.sessions import RANK

ROOT = Path(__file__).resolve().parents[3]
TYPES_TS = ROOT / "apps" / "dashboard" / "src" / "mocks" / "types.ts"
TS_ONLY = {"Page", "CrawlJob"}  # Page<T> is generic in TypeScript; the crawler is prototype-only
TS_OBJECT = re.compile(r"export type (\w+)(?:<\w+>)? = \{")
TS_FIELD = re.compile(r"^\s*(\w+)(\??):\s*(.+?);?\s*$")


def ts_objects(source: str) -> dict[str, dict[str, tuple[bool, str]]]:
    """{type name: {field: (optional, type text)}} for every `export type X = { ... }` block."""
    out: dict[str, dict[str, tuple[bool, str]]] = {}
    for match in TS_OBJECT.finditer(source):
        depth, i = 1, match.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(source[i], 0)
            i += 1
        fields = {}
        for line in source[match.end() : i - 1].splitlines():
            if m := TS_FIELD.match(line):
                fields[m.group(1)] = (m.group(2) == "?", m.group(3))
        out[match.group(1)] = fields
    return out


def wire_models() -> dict[str, type[schemas.Wire]]:
    return {
        name: obj
        for name, obj in vars(schemas).items()
        if isinstance(obj, type) and issubclass(obj, schemas.Wire) and obj is not schemas.Wire
    }


def top_level(ts_type: str) -> str:
    """The type text without generic arguments: `Record<K, V | null>` is not itself nullable."""
    while (inner := re.sub(r"<[^<>]*>", "", ts_type)) != ts_type:
        ts_type = inner
    return ts_type


def nullable(annotation: Any) -> bool:
    return get_origin(annotation) in (Union, types.UnionType) and type(None) in get_args(annotation)


def test_openapi_file_is_current() -> None:
    generated = render(create_app(ApiTestSettings()))  # type: ignore[call-arg]
    committed = (ROOT / CONTRACT).read_text(encoding="utf-8")
    assert committed == generated, "contracts/openapi.yaml is stale: run `python -m fw_coordinator.contract`"


def test_typescript_types_match_the_wire_models() -> None:
    ts = ts_objects(TYPES_TS.read_text(encoding="utf-8"))
    problems: list[str] = []
    models = wire_models()
    for name, model in models.items():
        if name.endswith("Page"):
            fields = set(model.model_fields)
            if fields != set(ts["Page"]):
                problems.append(f"{name}: fields {sorted(fields)} != Page<T> {sorted(ts['Page'])}")
            continue
        if name not in ts:
            problems.append(f"{name}: missing from types.ts")
            continue
        py_fields, ts_fields = model.model_fields, ts[name]
        if set(py_fields) != set(ts_fields):
            problems.append(f"{name}: python {sorted(py_fields)} != typescript {sorted(ts_fields)}")
            continue
        for field, info in py_fields.items():
            optional, text = ts_fields[field]
            ts_nullable = optional or re.search(r"\bnull\b", top_level(text)) is not None
            if nullable(info.annotation) != ts_nullable:
                problems.append(
                    f"{name}.{field}: nullable in python={nullable(info.annotation)}, typescript={ts_nullable}"
                )
    for extra in set(ts) - set(models) - TS_ONLY:
        problems.append(f"{extra}: in types.ts but not on the wire")
    assert not problems, "\n".join(problems)


def test_the_dashboard_ranks_roles_like_the_server() -> None:
    """roles.ts hides controls the server would refuse; a drift would show buttons that always fail."""
    source = (ROOT / "apps" / "dashboard" / "src" / "lib" / "live" / "roles.ts").read_text(encoding="utf-8")
    found = re.search(r"const RANK[^=]*=\s*\{([^}]*)\}", source)
    assert found, "RANK not found in roles.ts"
    dashboard = {k: int(v) for k, v in re.findall(r"(\w+)\s*:\s*(\d+)", found.group(1))}
    assert dashboard == RANK
