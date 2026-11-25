"""Rebuild config/assistant-knowledge.json from the approved public docs listed in config/assistant.yaml.

Usage: uv run python tools/dev/build_assistant_knowledge.py
Run it after editing any listed document; a coordinator test fails while the index is stale."""

from __future__ import annotations

import json
from pathlib import Path

from fw_coordinator.assistant import AssistantCopy
from fw_coordinator.assistant_knowledge import KNOWLEDGE_FILE, build
from fw_core.data import load_yaml

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    copy = load_yaml(ROOT / "config", "assistant.yaml", AssistantCopy)
    data = build(ROOT, copy.knowledge_sources, copy.version)
    out = ROOT / "config" / KNOWLEDGE_FILE
    out.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8", newline="\n")
    print(f"{out.relative_to(ROOT)}: {len(data['sections'])} sections from {len(data['sources'])} documents")


if __name__ == "__main__":
    main()
