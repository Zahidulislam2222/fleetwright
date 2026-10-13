"""Safety/refusal checks; the sustained browser run is a separate measured artifact."""

import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from loadtest.density import DensityConfig, atomic_json, cgroup_memory, require_resources


def test_resource_floor_and_ceiling_refuse_without_weakening_limits() -> None:
    cfg = DensityConfig.model_validate_json(Path("loadtest/density.json").read_text())
    with pytest.raises(RuntimeError, match="floor"):
        require_resources(cfg, {"available_bytes": cfg.minimum_available_bytes - 1, "enforced_memory_bytes": 0})
    with pytest.raises(RuntimeError, match="ceiling"):
        require_resources(
            cfg,
            {
                "available_bytes": cfg.minimum_available_bytes,
                "enforced_memory_bytes": cfg.maximum_process_rss_bytes + 1,
            },
        )


def test_cgroup_charge_counts_shared_memory_once_and_includes_swap(tmp_path: Path) -> None:
    cfg = DensityConfig.model_validate_json(Path("loadtest/density.json").read_text())
    (tmp_path / "memory.max").write_text(str(cfg.maximum_process_rss_bytes))
    (tmp_path / "memory.current").write_text("2000000000")
    (tmp_path / "memory.swap.current").write_text("100000000")
    measured = cgroup_memory(tmp_path)
    assert measured == 2100000000
    require_resources(
        cfg,
        {
            "available_bytes": cfg.minimum_available_bytes,
            "rss_bytes": cfg.maximum_process_rss_bytes * 2,
            "enforced_memory_bytes": measured,
        },
    )
    (tmp_path / "memory.swap.current").write_text(str(cfg.maximum_process_rss_bytes))
    with pytest.raises(RuntimeError, match="ceiling"):
        require_resources(
            cfg,
            {"available_bytes": cfg.minimum_available_bytes, "enforced_memory_bytes": cgroup_memory(tmp_path)},
        )


def test_cgroup_accounting_failure_refuses_instead_of_falling_back(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="accounting"):
        cgroup_memory(tmp_path)
    (tmp_path / "memory.max").write_text("max")
    (tmp_path / "memory.current").write_text("1")
    (tmp_path / "memory.swap.current").write_text("0")
    with pytest.raises(RuntimeError, match="accounting"):
        cgroup_memory(tmp_path)


def test_progress_replacement_is_atomic_and_config_is_strict(tmp_path: Path) -> None:
    path = tmp_path / "progress.json"
    atomic_json(path, {"status": "starting"})
    atomic_json(path, {"status": "running"})
    assert '"running"' in path.read_text()
    assert not path.with_suffix(".tmp").exists()
    data = json.loads(Path("loadtest/density.json").read_text())
    data["unknown_limit"] = 1
    with pytest.raises(ValidationError):
        DensityConfig.model_validate(data)
