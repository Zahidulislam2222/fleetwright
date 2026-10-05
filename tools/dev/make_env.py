"""Create a working local `.env` from `.env.example`, filling every __NAME__ placeholder with a fresh
random secret. Refuses to overwrite an existing .env. Secret values are never printed."""

import base64
import re
import secrets
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    target = ROOT / ".env"
    if target.exists():
        sys.exit(".env already exists; remove it first if you really want new secrets.")
    template = (ROOT / ".env.example").read_text(encoding="utf-8")
    values: dict[str, str] = {}

    def secret(match: re.Match[str]) -> str:
        name = match.group(1)
        if name not in values:
            values[name] = (
                base64.b64encode(secrets.token_bytes(32)).decode() if name.endswith("_B64") else secrets.token_urlsafe(32)
            )
        return values[name]

    target.write_text(re.sub(r"__([A-Z0-9_]+)__", secret, template), encoding="utf-8")
    print(f"wrote {target.name} with {len(values)} generated secrets (values not shown)")


if __name__ == "__main__":
    main()
