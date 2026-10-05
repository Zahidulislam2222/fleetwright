"""Worker tests run a real mock board and the real database: reuse both test kits."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "packages" / "fw_core" / "tests"), str(ROOT / "apps" / "mockboard" / "tests")]

from boardkit import board, default_rules  # noqa: E402 - must follow the path setup above
from dbkit import db  # noqa: E402

__all__ = ["board", "db", "default_rules"]
