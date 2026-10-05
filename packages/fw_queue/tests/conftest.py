"""The database test kit lives with fw_core's tests; make it importable here and share its fixture."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "fw_core" / "tests"))

from dbkit import db

__all__ = ["db"]
