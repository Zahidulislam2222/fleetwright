"""Approval identity must be identical across workers with different Python hash seeds."""

import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]


def test_workflow_fingerprints_are_deterministic_across_processes() -> None:
    script = (
        "import json,sys; from pathlib import Path; "
        "from fw_core.workflow_contracts import load_workflows; "
        "specs=load_workflows(Path(sys.argv[1])); "
        "print(json.dumps({name:spec.fingerprint for name,spec in specs.workflows.items()},sort_keys=True))"
    )
    fingerprints = []
    for seed in range(8):
        result = subprocess.run(
            [sys.executable, "-c", script, str(ROOT / "config")],
            env={**os.environ, "PYTHONHASHSEED": str(seed)},
            capture_output=True,
            text=True,
            check=True,
        )
        fingerprints.append(json.loads(result.stdout))
    assert all(value == fingerprints[0] for value in fingerprints), "contract identity depends on worker hash seed"
