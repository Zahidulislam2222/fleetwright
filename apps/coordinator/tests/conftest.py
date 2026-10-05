"""Coordinator tests use the shared database and board test kits, plus the API kit."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "packages" / "fw_core" / "tests"), str(ROOT / "apps" / "mockboard" / "tests")]

from apikit import api  # noqa: E402 - must follow the path setup above
from boardkit import board  # noqa: E402
from dbkit import db  # noqa: E402

__all__ = ["api", "board", "db"]
