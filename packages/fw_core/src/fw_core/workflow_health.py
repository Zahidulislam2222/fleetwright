"""Tenant-scoped operational gauges and actionable alerts, with bounded metric labels."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from fw_core.settings import WorkflowSettings
from fw_core.workflow_contracts import OperatorMessages


async def snapshot(
    conn: AsyncConnection, tenant: UUID, cfg: WorkflowSettings, messages: OperatorMessages
) -> dict[str, Any]:
    rows = (
        await conn.execute(
            text("""SELECT state,count(*) AS total,coalesce(max(extract(epoch FROM clock_timestamp()-updated_at)),0) AS age_s
                FROM workflow_jobs WHERE tenant_id=:t GROUP BY state"""),
            {"t": tenant},
        )
    ).all()
    counts = {r.state: int(r.total) for r in rows}
    ages = {r.state: float(r.age_s) for r in rows}
    claims_unknown = await conn.scalar(
        text("SELECT count(*) FROM claims WHERE tenant_id=:t AND state='UNKNOWN'"), {"t": tenant}
    )
    outbox_pending = await conn.scalar(
        text("SELECT count(*) FROM outbox WHERE tenant_id=:t AND published_at IS NULL"), {"t": tenant}
    )
    alerts = []
    if counts.get("UNKNOWN", 0) and ages.get("UNKNOWN", 0) >= cfg.alert_unknown_after_s:
        alerts.append(
            {
                "kind": "unknown_outcome",
                "severity": "critical",
                "count": counts["UNKNOWN"],
                "action": messages.unknown_outcome,
            }
        )
    if counts.get("QUEUED", 0) and ages.get("QUEUED", 0) >= cfg.approval_ttl_s:
        alerts.append(
            {
                "kind": "queued_stalled",
                "severity": "warning",
                "count": counts["QUEUED"],
                "action": messages.queued_stalled,
            }
        )
    return {
        "counts": counts,
        "oldest_state_age_s": ages,
        "freight_unknown": int(claims_unknown or 0),
        "outbox_pending": int(outbox_pending or 0),
        "alerts": alerts,
    }


def prometheus(data: dict[str, Any]) -> str:
    lines = ["# HELP fleetwright_workflow_jobs Current jobs by state.", "# TYPE fleetwright_workflow_jobs gauge"]
    for state in ("PENDING", "QUEUED", "LEASED", "ACTING", "CONFIRMED", "FAILED", "UNKNOWN", "CANCELLED"):
        lines.append(f'fleetwright_workflow_jobs{{state="{state}"}} {data["counts"].get(state, 0)}')
    lines.extend(
        [
            f"fleetwright_freight_unknown {data['freight_unknown']}",
            f"fleetwright_outbox_pending {data['outbox_pending']}",
            f"fleetwright_workflow_alerts {len(data['alerts'])}",
        ]
    )
    return "\n".join(lines) + "\n"
