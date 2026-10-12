"""Postgres-authoritative workflow execution. All calls require a tenant transaction.

The application role cannot bypass RLS. State, evidence and audit commit together. No external
action is executed in a database transaction: ACTING is committed before crossing that boundary.
"""

from __future__ import annotations

import hashlib
import json
import secrets
from dataclasses import dataclass
from typing import Any, Literal
from uuid import UUID, uuid4

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from fw_core.settings import WorkflowSettings
from fw_core.workflow_contracts import WorkflowSpec, digest

Scope = Literal["observe", "execute"]
SCOPES = frozenset({"observe", "execute"})
FINAL = frozenset({"CONFIRMED", "FAILED", "CANCELLED"})


class Denied(Exception):
    """Absent, expired, revoked or insufficient access. No cross-tenant information."""


class Conflict(Exception):
    """An identity or approval no longer matches the proposed action."""


@dataclass(frozen=True)
class Access:
    tenant: UUID
    grant: UUID
    user: UUID
    scopes: frozenset[str]


@dataclass(frozen=True)
class Held:
    tenant: UUID
    job: UUID
    fence: int
    worker: str


async def issue_access(
    conn: AsyncConnection, tenant: UUID, user: UUID, scopes: frozenset[str], ttl_s: int
) -> tuple[UUID, str]:
    if not scopes or not scopes <= SCOPES or ttl_s <= 0:
        raise ValueError("invalid scopes or expiry")
    allowed = await conn.scalar(
        text("SELECT id FROM users WHERE tenant_id=:t AND id=:u AND role IN ('owner','operator')"),
        {"t": tenant, "u": user},
    )
    if allowed is None:
        raise Denied("access denied")
    token, grant = secrets.token_urlsafe(32), uuid4()
    await conn.execute(
        text("""INSERT INTO workflow_grants(tenant_id,id,user_id,token_hash,scopes,expires_at)
                VALUES (:t,:g,:u,:h,CAST(:s AS text[]),clock_timestamp()+make_interval(secs=>:ttl))"""),
        {
            "t": tenant,
            "g": grant,
            "u": user,
            "h": hashlib.sha256(token.encode()).hexdigest(),
            "s": list(scopes),
            "ttl": ttl_s,
        },
    )
    await _audit(conn, tenant, str(user), "workflow.grant_issued", str(grant))
    return grant, token


async def authorize(conn: AsyncConnection, tenant: UUID, token: str, scope: Scope) -> Access:
    if not token or len(token) > 200:
        raise Denied("access denied")
    row = (
        await conn.execute(
            text("""SELECT g.id,g.user_id,g.scopes FROM workflow_grants g JOIN users u
                ON (u.tenant_id,u.id)=(g.tenant_id,g.user_id)
                WHERE g.tenant_id=:t AND g.token_hash=:h AND g.revoked_at IS NULL
                  AND g.expires_at>clock_timestamp() AND u.role IN ('owner','operator')"""),
            {"t": tenant, "h": hashlib.sha256(token.encode()).hexdigest()},
        )
    ).one_or_none()
    if row is None or scope not in row.scopes:
        raise Denied("access denied")
    return Access(tenant, row.id, row.user_id, frozenset(row.scopes))


async def revoke_access(conn: AsyncConnection, tenant: UUID, grant: UUID, actor: UUID) -> None:
    await conn.execute(
        text("UPDATE workflow_grants SET revoked_at=clock_timestamp() WHERE tenant_id=:t AND id=:g"),
        {"t": tenant, "g": grant},
    )
    await _audit(conn, tenant, str(actor), "workflow.grant_revoked", str(grant))


async def _audit(conn: AsyncConnection, tenant: UUID, actor: str, action: str, target: str) -> None:
    await conn.execute(
        text("""INSERT INTO audit_log(tenant_id,actor,role,action,target,detail)
                VALUES (:t,:a,'workflow',:s,:j,'workflow state and audit committed together')"""),
        {"t": tenant, "a": actor, "s": action, "j": target},
    )


async def event(conn: AsyncConnection, tenant: UUID, job: UUID, kind: str, evidence: dict[str, Any]) -> None:
    # Deliberate allowlist: never persist target HTML, headers, cookies, arbitrary exception text,
    # screenshots or user-entered content. Destination text is untrusted and may contain secrets.
    safe = {
        k: v
        for k, v in evidence.items()
        if k
        in {"state", "fence", "status", "receipt_hash", "action_hash", "contract_hash", "reason", "verified", "attempt"}
    }
    if len(json.dumps(safe)) > 4096:
        raise ValueError("evidence too large")
    await conn.execute(
        text("INSERT INTO workflow_events(tenant_id,job_id,kind,evidence) VALUES (:t,:j,:k,CAST(:e AS jsonb))"),
        {"t": tenant, "j": job, "k": kind, "e": json.dumps(safe)},
    )
    await _audit(conn, tenant, "workflow", kind, str(job))


async def submit(
    conn: AsyncConnection,
    access: Access,
    identity: str,
    workflow: str,
    spec: WorkflowSpec,
    account: UUID,
    inputs: dict[str, str],
) -> dict[str, Any]:
    if "execute" not in access.scopes:
        raise Denied("access denied")
    if not identity or len(identity) > 120:
        raise ValueError("invalid action identity")
    values = spec.validate_inputs(inputs)
    target = await conn.scalar(
        text("SELECT target FROM accounts WHERE tenant_id=:t AND id=:a AND enabled"), {"t": access.tenant, "a": account}
    )
    if target != spec.target:
        raise Denied("account is not permitted by this contract")
    action_hash = digest(
        {
            "tenant": str(access.tenant),
            "workflow": workflow,
            "contract": spec.fingerprint,
            "account": str(account),
            "inputs": values,
        }
    )
    job = uuid4()
    row = (
        await conn.execute(
            text("""INSERT INTO workflow_jobs(tenant_id,id,grant_id,identity,workflow,contract_hash,action_hash,account_id,inputs,state)
                VALUES (:t,:j,:g,:i,:w,:c,:h,:a,CAST(:v AS jsonb),'PENDING')
                ON CONFLICT (tenant_id,identity) DO NOTHING RETURNING id"""),
            {
                "t": access.tenant,
                "j": job,
                "g": access.grant,
                "i": identity,
                "w": workflow,
                "c": spec.fingerprint,
                "h": action_hash,
                "a": account,
                "v": json.dumps(values),
            },
        )
    ).one_or_none()
    if row is None:
        existing = (
            await conn.execute(
                text("SELECT id,action_hash FROM workflow_jobs WHERE tenant_id=:t AND identity=:i"),
                {"t": access.tenant, "i": identity},
            )
        ).one()
        if existing.action_hash != action_hash:
            raise Conflict("identity already binds a different action")
        job = existing.id
    else:
        await event(
            conn,
            access.tenant,
            job,
            "submitted",
            {"state": "PENDING", "action_hash": action_hash, "contract_hash": spec.fingerprint},
        )
    return await inspect(conn, access.tenant, job)


async def list_page(conn: AsyncConnection, tenant: UUID, limit: int, cursor: UUID | None = None) -> dict[str, Any]:
    if cursor is not None:
        await inspect(conn, tenant, cursor)
    rows = list(
        (
            await conn.execute(
                text("""SELECT id FROM workflow_jobs WHERE tenant_id=:t
        AND (CAST(:cursor AS uuid) IS NULL OR (created_at,id)<
             (SELECT created_at,id FROM workflow_jobs WHERE tenant_id=:t AND id=:cursor))
        ORDER BY created_at DESC,id DESC LIMIT :n"""),
                {"t": tenant, "cursor": cursor, "n": limit + 1},
            )
        ).scalars()
    )
    return {
        "jobs": [await inspect(conn, tenant, key) for key in rows[:limit]],
        "next_cursor": str(rows[limit - 1]) if len(rows) > limit else None,
    }


async def inspect(conn: AsyncConnection, tenant: UUID, job: UUID) -> dict[str, Any]:
    row = (
        (
            await conn.execute(
                text("""SELECT id,identity,workflow,account_id,state,action_hash,contract_hash,cancel_requested,created_at,updated_at
                FROM workflow_jobs WHERE tenant_id=:t AND id=:j"""),
                {"t": tenant, "j": job},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        raise Denied("job unavailable")
    return {k: (str(v) if isinstance(v, UUID) or hasattr(v, "isoformat") else v) for k, v in row.items()}


async def approve(conn: AsyncConnection, tenant: UUID, job: UUID, expected_hash: str, user: UUID, ttl_s: int) -> None:
    if ttl_s <= 0:
        raise ValueError("approval expiry must be positive")
    owner = await conn.scalar(
        text("SELECT id FROM users WHERE tenant_id=:t AND id=:u AND role='owner'"), {"t": tenant, "u": user}
    )
    if owner is None:
        raise Denied("human owner approval required")
    changed = await conn.scalar(
        text("""UPDATE workflow_jobs SET state='QUEUED',updated_at=clock_timestamp()
                WHERE tenant_id=:t AND id=:j AND state='PENDING' AND action_hash=:h RETURNING id"""),
        {"t": tenant, "j": job, "h": expected_hash},
    )
    if changed is None:
        raise Conflict("approval is changed, replayed or job is no longer pending")
    await conn.execute(
        text("""INSERT INTO workflow_approvals(tenant_id,job_id,action_hash,approver_id,expires_at)
                VALUES (:t,:j,:h,:u,clock_timestamp()+make_interval(secs=>:ttl))
                ON CONFLICT (tenant_id,job_id) DO UPDATE SET action_hash=EXCLUDED.action_hash,
                approver_id=EXCLUDED.approver_id,expires_at=EXCLUDED.expires_at,revoked_at=NULL
                WHERE workflow_approvals.consumed_at IS NULL"""),
        {"t": tenant, "j": job, "h": expected_hash, "u": user, "ttl": ttl_s},
    )
    await event(conn, tenant, job, "approved", {"state": "QUEUED", "action_hash": expected_hash})


async def revoke_approval(conn: AsyncConnection, tenant: UUID, job: UUID) -> None:
    await conn.execute(
        text("UPDATE workflow_approvals SET revoked_at=clock_timestamp() WHERE tenant_id=:t AND job_id=:j"),
        {"t": tenant, "j": job},
    )
    await event(conn, tenant, job, "approval_revoked", {})


async def ready_jobs(conn: AsyncConnection, tenant: UUID, limit: int) -> list[UUID]:
    rows = await conn.execute(
        text("""SELECT j.id FROM workflow_jobs j
        JOIN workflow_approvals a ON (a.tenant_id,a.job_id)=(j.tenant_id,j.id)
        JOIN workflow_grants g ON (g.tenant_id,g.id)=(j.tenant_id,j.grant_id)
        JOIN users u ON (u.tenant_id,u.id)=(g.tenant_id,g.user_id)
        JOIN users owner ON (owner.tenant_id,owner.id)=(a.tenant_id,a.approver_id)
        JOIN accounts account ON (account.tenant_id,account.id)=(j.tenant_id,j.account_id)
        WHERE j.tenant_id=:t AND j.state='QUEUED' AND NOT j.cancel_requested
          AND a.expires_at>clock_timestamp() AND a.consumed_at IS NULL AND a.revoked_at IS NULL
          AND a.action_hash=j.action_hash AND g.expires_at>clock_timestamp() AND g.revoked_at IS NULL
          AND 'execute'=ANY(g.scopes) AND u.role IN ('owner','operator') AND owner.role='owner' AND account.enabled
          AND (account.holder_worker IS NULL OR account.holder_expires_at<clock_timestamp())
          AND NOT EXISTS (SELECT 1 FROM workflow_jobs active WHERE active.tenant_id=:t
                           AND active.account_id=j.account_id AND active.state IN ('LEASED','ACTING'))
        ORDER BY j.created_at,j.id LIMIT :n"""),
        {"t": tenant, "n": limit},
    )
    return list(rows.scalars())


async def reconciliation_batch(conn: AsyncConnection, tenant: UUID, cfg: WorkflowSettings) -> list[dict[str, Any]]:
    rows = await conn.execute(
        text("""WITH candidates AS (
        SELECT id FROM workflow_jobs WHERE tenant_id=:t AND state='UNKNOWN'
          AND updated_at<clock_timestamp()-make_interval(secs=>:grace)
          AND (last_reconciled_at IS NULL OR last_reconciled_at<clock_timestamp()-make_interval(secs=>:poll))
        ORDER BY last_reconciled_at NULLS FIRST,created_at,id LIMIT :n FOR UPDATE SKIP LOCKED
        ) UPDATE workflow_jobs j SET last_reconciled_at=clock_timestamp() FROM candidates c
          WHERE j.tenant_id=:t AND j.id=c.id RETURNING j.*"""),
        {"t": tenant, "n": cfg.evidence_page_size, "grace": cfg.reconcile_grace_s, "poll": cfg.poll_s},
    )
    return [dict(row) for row in rows.mappings()]


async def reject_before_action(conn: AsyncConnection, held: Held) -> None:
    account = await conn.scalar(
        text("""UPDATE workflow_jobs SET state='PENDING',updated_at=clock_timestamp()
        WHERE tenant_id=:t AND id=:j AND fence=:f AND worker_id=:w AND state='LEASED' RETURNING account_id"""),
        {"t": held.tenant, "j": held.job, "f": held.fence, "w": held.worker},
    )
    if account is not None:
        await _release(conn, held.tenant, account, held.worker)
        await revoke_approval(conn, held.tenant, held.job)
        await event(conn, held.tenant, held.job, "authorization_rejected", {"state": "PENDING"})


async def take(conn: AsyncConnection, tenant: UUID, job: UUID, worker: str, ttl_s: float) -> Held | None:
    row = (
        await conn.execute(
            text("""SELECT account_id FROM workflow_jobs WHERE tenant_id=:t AND id=:j AND state='QUEUED'
                FOR UPDATE SKIP LOCKED"""),
            {"t": tenant, "j": job},
        )
    ).one_or_none()
    if row is None:
        return None
    if not await _take_account(conn, tenant, row.account_id, worker, ttl_s):
        return None
    fence = await conn.scalar(
        text("""UPDATE workflow_jobs SET state='LEASED',worker_id=:w,fence=nextval('workflow_fence'),
                lease_expires_at=clock_timestamp()+make_interval(secs=>:ttl),updated_at=clock_timestamp()
                WHERE tenant_id=:t AND id=:j RETURNING fence"""),
        {"t": tenant, "j": job, "w": worker, "ttl": ttl_s},
    )
    await event(conn, tenant, job, "leased", {"state": "LEASED", "fence": fence})
    return Held(tenant, job, int(fence), worker)


async def _take_account(conn: AsyncConnection, tenant: UUID, account: UUID, worker: str, ttl_s: float) -> bool:
    held = await conn.scalar(
        text("""UPDATE accounts SET holder_worker=:w,holder_expires_at=clock_timestamp()+make_interval(secs=>:ttl)
                WHERE tenant_id=:t AND id=:a AND enabled AND (holder_worker IS NULL OR holder_expires_at<clock_timestamp())
                  AND NOT EXISTS (SELECT 1 FROM claims WHERE tenant_id=:t AND account_id=:a AND state IN ('LEASED','ACTING'))
                  AND NOT EXISTS (SELECT 1 FROM workflow_jobs WHERE tenant_id=:t AND account_id=:a AND state IN ('LEASED','ACTING'))
                RETURNING id"""),
        {"t": tenant, "a": account, "w": worker, "ttl": ttl_s},
    )
    return held is not None


async def reserve_reconciliation_account(
    conn: AsyncConnection, tenant: UUID, job: UUID, worker: str, ttl_s: float
) -> UUID | None:
    account: UUID | None = await conn.scalar(
        text("SELECT account_id FROM workflow_jobs WHERE tenant_id=:t AND id=:j AND state='UNKNOWN'"),
        {"t": tenant, "j": job},
    )
    if account is None or not await _take_account(conn, tenant, account, worker, ttl_s):
        return None
    return account


async def release_reconciliation_account(conn: AsyncConnection, tenant: UUID, account: UUID, worker: str) -> None:
    await _release(conn, tenant, account, worker)


async def account_owned(conn: AsyncConnection, tenant: UUID, account: UUID, worker: str) -> bool:
    return (
        await conn.scalar(
            text("""SELECT id FROM accounts WHERE tenant_id=:t AND id=:a AND enabled
        AND holder_worker=:w AND holder_expires_at>clock_timestamp() FOR UPDATE"""),
            {"t": tenant, "a": account, "w": worker},
        )
        is not None
    )


async def begin_action(conn: AsyncConnection, held: Held, spec: WorkflowSpec, cfg: WorkflowSettings) -> bool:
    p = {"t": held.tenant, "j": held.job, "f": held.fence, "w": held.worker, "c": spec.fingerprint}
    # Lock the approval and grant until ACTING commits. Concurrent revocation serializes here.
    row = (
        await conn.execute(
            text("""SELECT j.action_hash FROM workflow_jobs j JOIN workflow_approvals a
                  ON (a.tenant_id,a.job_id)=(j.tenant_id,j.id)
                JOIN workflow_grants g ON (g.tenant_id,g.id)=(j.tenant_id,j.grant_id)
                JOIN users u ON (u.tenant_id,u.id)=(a.tenant_id,a.approver_id)
                JOIN users requester ON (requester.tenant_id,requester.id)=(g.tenant_id,g.user_id)
                JOIN accounts account ON (account.tenant_id,account.id)=(j.tenant_id,j.account_id)
                WHERE j.tenant_id=:t AND j.id=:j AND j.fence=:f AND j.worker_id=:w
                  AND j.state='LEASED' AND j.lease_expires_at>clock_timestamp() AND NOT j.cancel_requested
                  AND j.contract_hash=:c AND a.action_hash=j.action_hash
                  AND a.expires_at>clock_timestamp() AND a.consumed_at IS NULL AND a.revoked_at IS NULL
                  AND g.expires_at>clock_timestamp() AND g.revoked_at IS NULL AND 'execute'=ANY(g.scopes)
                  AND u.role='owner' AND requester.role IN ('owner','operator')
                  AND account.enabled AND account.holder_worker=:w AND account.holder_expires_at>clock_timestamp()
                FOR UPDATE OF j,a,g,account"""),
            p,
        )
    ).one_or_none()
    if row is None:
        return False
    actual = (
        await conn.execute(text("SELECT workflow,account_id,inputs FROM workflow_jobs WHERE tenant_id=:t AND id=:j"), p)
    ).one()
    recalculated = digest(
        {
            "tenant": str(held.tenant),
            "workflow": actual.workflow,
            "contract": spec.fingerprint,
            "account": str(actual.account_id),
            "inputs": spec.validate_inputs(actual.inputs),
        }
    )
    if recalculated != row.action_hash:
        return False
    await conn.execute(
        text("UPDATE workflow_approvals SET consumed_at=clock_timestamp() WHERE tenant_id=:t AND job_id=:j"), p
    )
    await conn.execute(
        text("""UPDATE workflow_jobs SET state='ACTING',updated_at=clock_timestamp(),
        lease_expires_at=clock_timestamp()+make_interval(secs=>:ttl) WHERE tenant_id=:t AND id=:j"""),
        {**p, "ttl": cfg.lease_s},
    )
    await conn.execute(
        text("""UPDATE accounts SET holder_expires_at=clock_timestamp()+make_interval(secs=>:ttl)
        WHERE tenant_id=:t AND id=(SELECT account_id FROM workflow_jobs WHERE tenant_id=:t AND id=:j)
        AND holder_worker=:w"""),
        {**p, "ttl": cfg.lease_s},
    )
    await event(conn, held.tenant, held.job, "acting", {"state": "ACTING", "fence": held.fence})
    return True


async def finish(
    conn: AsyncConnection, held: Held, outcome: Literal["CONFIRMED", "FAILED", "UNKNOWN"], evidence: dict[str, Any]
) -> bool:
    row = await conn.scalar(
        text("""UPDATE workflow_jobs SET state=:s,updated_at=clock_timestamp()
                WHERE tenant_id=:t AND id=:j AND fence=:f AND worker_id=:w AND state='ACTING'
                  AND lease_expires_at>clock_timestamp() RETURNING account_id"""),
        {"t": held.tenant, "j": held.job, "f": held.fence, "w": held.worker, "s": outcome},
    )
    if row is None:
        return False
    await _release(conn, held.tenant, row, held.worker)
    await event(conn, held.tenant, held.job, "outcome", {**evidence, "state": outcome, "fence": held.fence})
    return True


async def _release(conn: AsyncConnection, tenant: UUID, account: UUID, worker: str) -> None:
    await conn.execute(
        text(
            "UPDATE accounts SET holder_worker=NULL,holder_expires_at=NULL WHERE tenant_id=:t AND id=:a AND holder_worker=:w"
        ),
        {"t": tenant, "a": account, "w": worker},
    )


async def cancel(conn: AsyncConnection, tenant: UUID, job: UUID) -> dict[str, Any]:
    row = (
        await conn.execute(
            text("""UPDATE workflow_jobs SET cancel_requested=true,
                state=CASE WHEN state IN ('PENDING','QUEUED','LEASED') THEN 'CANCELLED' ELSE state END,
                updated_at=clock_timestamp() WHERE tenant_id=:t AND id=:j RETURNING state,account_id,worker_id"""),
            {"t": tenant, "j": job},
        )
    ).one_or_none()
    if row is None:
        raise Denied("job unavailable")
    if row.state == "CANCELLED" and row.worker_id:
        await _release(conn, tenant, row.account_id, row.worker_id)
    await event(conn, tenant, job, "cancel_requested", {"state": row.state})
    return await inspect(conn, tenant, job)


async def recover(conn: AsyncConnection, tenant: UUID, limit: int) -> int:
    rows = (
        await conn.execute(
            text("""SELECT id,account_id,worker_id,state FROM workflow_jobs WHERE tenant_id=:t
                AND state IN ('LEASED','ACTING') AND lease_expires_at<=clock_timestamp()
                ORDER BY lease_expires_at LIMIT :n FOR UPDATE SKIP LOCKED"""),
            {"t": tenant, "n": limit},
        )
    ).all()
    for row in rows:
        state = "UNKNOWN" if row.state == "ACTING" else "QUEUED"
        await conn.execute(
            text("UPDATE workflow_jobs SET state=:s,updated_at=clock_timestamp() WHERE tenant_id=:t AND id=:j"),
            {"t": tenant, "j": row.id, "s": state},
        )
        await _release(conn, tenant, row.account_id, row.worker_id)
        await event(conn, tenant, row.id, "lease_expired", {"state": state})
    return len(rows)


async def reconcile(
    conn: AsyncConnection,
    tenant: UUID,
    job: UUID,
    action_hash: str,
    outcome: Literal["CONFIRMED", "FAILED"] | None,
    receipt_hash: str,
) -> bool:
    if outcome is None:
        # No unbounded event writes on every inconclusive poll. UNKNOWN remains inspectable.
        return False
    changed = await conn.scalar(
        text("""UPDATE workflow_jobs SET state=:s,updated_at=clock_timestamp()
                WHERE tenant_id=:t AND id=:j AND state='UNKNOWN' AND action_hash=:h RETURNING id"""),
        {"t": tenant, "j": job, "s": outcome, "h": action_hash},
    )
    if changed is None:
        return False
    await event(conn, tenant, job, "reconciled", {"state": outcome, "receipt_hash": receipt_hash, "verified": True})
    return True


async def evidence_page(
    conn: AsyncConnection, tenant: UUID, job: UUID, cursor: int, cfg: WorkflowSettings
) -> dict[str, Any]:
    info = await inspect(conn, tenant, job)
    rows = (
        (
            await conn.execute(
                text("""SELECT id,at,kind,evidence FROM workflow_events WHERE tenant_id=:t AND job_id=:j AND id>:c
                ORDER BY id LIMIT :n"""),
                {"t": tenant, "j": job, "c": max(0, cursor), "n": cfg.evidence_page_size + 1},
            )
        )
        .mappings()
        .all()
    )
    more = len(rows) > cfg.evidence_page_size
    items = [{**r, "at": r["at"].isoformat()} for r in rows[: cfg.evidence_page_size]]
    page = {"job": info, "events": items, "next_cursor": items[-1]["id"] if more else None}
    return {**page, "sha256": digest(page), "integrity": "page content hash; not an authenticity signature"}
