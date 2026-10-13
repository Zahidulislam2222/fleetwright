"""Reuse the project's isolated database fixture for real local capacity verification."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT / "packages" / "fw_core" / "tests")]

from dbkit import db  # noqa: E402

__all__ = ["db"]
