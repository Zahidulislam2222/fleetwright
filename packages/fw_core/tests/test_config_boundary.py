"""Rule 12 regression test: business code must not contain endpoints, hosts, ports or secrets.
It inspects string literals (docstrings excluded) in every service and package source tree."""

from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SOURCE_DIRS = [*ROOT.glob("packages/*/src"), *ROOT.glob("apps/*/src")]

FORBIDDEN = [
    ("url", re.compile(r"\b(?:https?|wss?|redis|rediss|postgres(?:ql)?(?:\+\w+)?|smtp|imaps?)://", re.I)),
    (
        "loopback/private host",
        re.compile(r"\b(?:localhost|127\.0\.0\.1|0\.0\.0\.0|10\.\d+\.\d+\.\d+|192\.168\.\d+\.\d+)\b"),
    ),
    ("host:port", re.compile(r"\b[a-z][\w.-]*:\d{2,5}\b", re.I)),
    ("model id", re.compile(r"\b(?:gpt-\d|claude-[a-z]|llama\d|gemini-\d|qwen\d)", re.I)),
    ("private key", re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
    ("aws key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("long secret-like literal", re.compile(r"^[A-Za-z0-9+/_=-]{40,}$")),
]


def scan_source(source: str) -> list[tuple[int, str, str]]:
    tree = ast.parse(source)
    docstrings: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)) and node.body:
            first = node.body[0]
            if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant):
                docstrings.add(id(first.value))
    hits = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and id(node) not in docstrings:
            for label, pattern in FORBIDDEN:
                if pattern.search(node.value):
                    hits.append((node.lineno, label, node.value[:60]))
    return hits


def test_scanner_catches_injected_values() -> None:
    sample = (
        'BOARD = "http://127.0.0.1:8100"\nMODEL = "gpt-5-mini"\nREDIS = "redis-core:6379"\nK = "AKIA' + "A" * 16 + '"\n'
    )
    labels = {label for _, label, _ in scan_source(sample)}
    assert {"url", "loopback/private host", "host:port", "model id", "aws key"} <= labels


def test_business_code_has_no_hardcoded_endpoints_or_secrets() -> None:
    problems = []
    for src in SOURCE_DIRS:
        for path in src.rglob("*.py"):
            for line, label, value in scan_source(path.read_text(encoding="utf-8")):
                problems.append(f"{path.relative_to(ROOT)}:{line} {label}: {value!r}")
    assert not problems, "hardcoded configuration found:\n" + "\n".join(problems)
