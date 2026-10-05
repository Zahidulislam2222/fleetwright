"""Fill deploy/env/*.env.example into a directory of real env files for the VPS, with one shared set
of fresh secrets (so the Postgres role passwords and the DSNs agree). Refuses to overwrite.
Secret values are never printed. Record them in CREDENTIALS.md afterwards (Rule 8).

    python deploy/make_vps_env.py <out-dir>
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools" / "dev"))
from make_env import fill  # noqa: E402 - path set above

TEMPLATES = ("fleetwright.env", "postgres.env")


def main() -> None:
    if len(sys.argv) != 2:
        sys.exit(__doc__)
    out = Path(sys.argv[1])
    targets = [out / name for name in TEMPLATES]
    if any(t.exists() for t in targets):
        sys.exit(f"{out} already has env files; remove them deliberately to rotate every secret.")
    out.mkdir(parents=True, exist_ok=True)
    values: dict[str, str] = {}
    for name, target in zip(TEMPLATES, targets, strict=True):
        target.write_text(
            fill((ROOT / "deploy" / "env" / f"{name}.example").read_text(encoding="utf-8"), values), encoding="utf-8"
        )
    print(f"wrote {', '.join(TEMPLATES)} to {out} with {len(values)} generated secrets (values not shown)")


if __name__ == "__main__":
    main()
