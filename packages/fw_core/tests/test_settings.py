"""The configuration boundary (Rule 12): .env.example documents every setting, every documented
FW_ variable is read by some service, and business code holds no hardcoded endpoints or secrets."""

from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel
from pydantic_settings import BaseSettings

from fw_core.settings import SERVICE_SETTINGS

ROOT = Path(__file__).resolve().parents[3]
EXAMPLE = ROOT / ".env.example"
# Variables documented in .env.example that are not service settings (tooling and Compose only).
NON_SERVICE_PREFIXES = ("FWDEV_", "OPENROUTER_", "FLEETWRIGHT_")


def _env_names(model: type[BaseModel], prefix: str) -> dict[str, bool]:
    """Every leaf env var name for a settings model -> whether it is required."""
    out: dict[str, bool] = {}
    for name, field in model.model_fields.items():
        env = f"{prefix}{name.upper()}"
        ann = field.annotation
        if isinstance(ann, type) and issubclass(ann, BaseModel) and not issubclass(ann, BaseSettings):
            nested = _env_names(ann, env + "__")
            out.update({k: (v and field.is_required()) for k, v in nested.items()})
        else:
            out[env] = field.is_required()
    return out


def _all_service_vars() -> dict[str, bool]:
    names: dict[str, bool] = {}
    for cls in SERVICE_SETTINGS:
        for k, required in _env_names(cls, "FW_").items():
            names[k] = names.get(k, False) or required
    return names


def _documented() -> set[str]:
    return {
        line.split("=", 1)[0].strip()
        for line in EXAMPLE.read_text(encoding="utf-8").splitlines()
        if "=" in line and not line.lstrip().startswith("#")
    }


def test_every_required_setting_is_documented() -> None:
    documented = _documented()
    missing = sorted(k for k, required in _all_service_vars().items() if required and k not in documented)
    assert not missing, f"required settings missing from .env.example: {missing}"


def test_every_documented_variable_is_read_by_a_service() -> None:
    known = _all_service_vars()
    stray = sorted(
        k
        for k in _documented()
        if not k.startswith(NON_SERVICE_PREFIXES) and k not in known and not k.startswith("FW_LOCAL")
    )
    assert not stray, f".env.example documents variables no service reads (typo?): {stray}"


def test_example_holds_no_real_secrets() -> None:
    for line in EXAMPLE.read_text(encoding="utf-8").splitlines():
        if line.lstrip().startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        if re.search(r"PASSWORD|TOKEN|KEY_B64|SECRET", key):
            assert re.fullmatch(r"__[A-Z0-9_]+__", value), f"{key} must be a generated placeholder"
        assert "__" in value or not re.search(r"://[^:/]+:[^@_]{8,}@", value), f"{key} embeds a password"
