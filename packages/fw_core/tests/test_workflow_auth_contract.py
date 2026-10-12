"""General workflow authentication must not require fictitious freight endpoints."""

from pathlib import Path

import pytest
import yaml

from fw_core.targets import load_targets

ROOT = Path(__file__).resolve().parents[3]


@pytest.mark.parametrize("has_captcha", [True, False])
def test_nonfreight_target_only_needs_authentication_contract(tmp_path: Path, has_captcha: bool) -> None:
    configured = yaml.safe_load((ROOT / "config/targets.yaml").read_text())
    legacy = configured["targets"]["demo-board"]
    generic = {
        "name": "Owned service portal",
        "login": legacy["login"],
        "captcha": legacy["captcha"] if has_captcha else None,
        "api": {"me": legacy["api"]["me"], "csrf_header": legacy["api"]["csrf_header"]},
    }
    configured["targets"]["service-only"] = generic
    (tmp_path / "targets.yaml").write_text(yaml.safe_dump(configured), encoding="utf-8")
    targets = load_targets(tmp_path)
    assert targets.authentication("service-only").api.me == legacy["api"]["me"]
    assert targets.get("demo-board").api.book == legacy["api"]["book"]
    with pytest.raises(ValueError, match="freight"):
        targets.get("service-only")
