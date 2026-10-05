"""Create a working local `.env` from `.env.example`, filling every __NAME__ placeholder with a fresh
random secret. Refuses to overwrite an existing .env. Secret values are never printed.

    python tools/dev/make_env.py           # new .env
    python tools/dev/make_env.py --sync    # add variables .env.example gained since; keep existing values
"""

import base64
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
PLACEHOLDER = re.compile(r"__([A-Z0-9_]+)__")
ASSIGNMENT = re.compile(r"^([A-Z0-9_]+)=(.*)$", re.MULTILINE)


def generate(name: str) -> str:
    if name.endswith("_B64"):
        return base64.b64encode(secrets.token_bytes(32)).decode()
    if name.endswith("_B32"):  # TOTP secrets: base32, 160 bits
        return base64.b32encode(secrets.token_bytes(20)).decode()
    return secrets.token_urlsafe(32)


def fill(text: str, values: dict[str, str]) -> str:
    return PLACEHOLDER.sub(lambda m: values.setdefault(m.group(1), generate(m.group(1))), text)


def create(target: Path, template: str) -> None:
    if target.exists():
        sys.exit(".env already exists; use --sync to add new variables, or remove it for all-new secrets.")
    values: dict[str, str] = {}
    target.write_text(fill(template, values), encoding="utf-8")
    print(f"wrote {target.name} with {len(values)} generated secrets (values not shown)")


def sync(target: Path, template: str) -> None:
    if not target.exists():
        sys.exit("no .env yet; run without --sync first")
    current = target.read_text(encoding="utf-8")
    have = {m.group(1) for m in ASSIGNMENT.finditer(current)}
    values: dict[str, str] = {}
    added = [
        f"{m.group(1)}={fill(m.group(2), values)}" for m in ASSIGNMENT.finditer(template) if m.group(1) not in have
    ]
    if added:
        target.write_text(current.rstrip("\n") + "\n" + "\n".join(added) + "\n", encoding="utf-8")
    print(f"added {len(added)} variables to {target.name} ({len(values)} generated secrets; values not shown)")


def main() -> None:
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    target = ROOT / ".env"
    if "--sync" in sys.argv[1:]:
        sync(target, template)
    else:
        create(target, template)


if __name__ == "__main__":
    main()
