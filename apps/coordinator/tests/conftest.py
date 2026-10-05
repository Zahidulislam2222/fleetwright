"""Coordinator tests use the shared database test kit."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
sys.path[:0] = [str(ROOT / "packages" / "fw_core" / "tests"), str(ROOT / "apps" / "mockboard" / "tests")]

from dbkit import db  # noqa: E402 - must follow the path setup above

__all__ = ["db"]
