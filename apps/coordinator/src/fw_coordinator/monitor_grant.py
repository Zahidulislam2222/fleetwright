"""Narrow observation-grant authority for the existing privileged host monitor.

JSON request and result use protected subprocess pipes. No bearer, DSN or password is accepted in
arguments. This helper never exposes an HTTP endpoint or grants execute/approval authority.
"""

from __future__ import annotations

import asyncio
import json
import sys
from uuid import UUID

from fw_core import workflows
from fw_core.db import make_engine, tenant_tx
from fw_core.settings import DatabaseSettings, MonitorAuthorityAppSettings, MonitorGrantSettings, load


async def issue(cfg: DatabaseSettings, grant: MonitorGrantSettings, predecessor: UUID | None) -> dict[str, str]:
    engine = make_engine(cfg.dsn, cfg, "fleetwright-monitor-authority")
    try:
        async with tenant_tx(engine, grant.tenant_id) as conn:
            if predecessor is not None:
                await workflows.revoke_access(conn, grant.tenant_id, predecessor, grant.user_id)
            identifier, token = await workflows.issue_access(
                conn, grant.tenant_id, grant.user_id, frozenset({"observe"}), grant.ttl_s
            )
        return {"grant_id": str(identifier), "token": token, "tenant_id": str(grant.tenant_id)}
    finally:
        await engine.dispose()


async def main() -> None:
    raw = sys.stdin.buffer.read(8193)
    if len(raw) > 8192:
        raise ValueError("oversized authority request")
    request = json.loads(raw)
    predecessor = UUID(request.pop("predecessor")) if request.get("predecessor") else None
    grant = MonitorGrantSettings.model_validate(request)
    result = await issue(load(MonitorAuthorityAppSettings).app_db, grant, predecessor)
    sys.stdout.write(json.dumps(result))


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception:
        # SQL errors may include sensitive connection/row details. Emit only a fixed category.
        sys.stderr.write("observation grant authority failed\n")
        raise SystemExit(1) from None
