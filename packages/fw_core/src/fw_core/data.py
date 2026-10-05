"""Loader for maintained product data (YAML under the configured config directory).
Files are validated with pydantic models owned by the service that uses them."""

from __future__ import annotations

from pathlib import Path

import yaml
from pydantic import BaseModel


def load_yaml[M: BaseModel](config_dir: Path, name: str, model: type[M]) -> M:
    path = config_dir / name
    with path.open(encoding="utf-8") as fh:
        return model.model_validate(yaml.safe_load(fh))
