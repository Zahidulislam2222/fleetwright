"""The `/v1` wire contract. These models are the single source of truth: FastAPI validates every
response against them, `contracts/openapi.yaml` is generated from them, and a test keeps the
console's TypeScript types (apps/dashboard/src/mocks/types.ts) in step. Display wording (stage
labels, alert titles) belongs to the console, so the wire carries keys and numbers only."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict

ClaimState = Literal["DETECTED", "QUEUED", "LEASED", "ACTING", "CONFIRMED", "FAILED", "UNKNOWN", "RECONCILED"]
UserRole = Literal["owner", "operator", "viewer", "demo"]
ViewerRole = Literal["public", "viewer", "demo", "operator", "owner"]


class Wire(BaseModel):
    model_config = ConfigDict(extra="forbid")


class Worker(Wire):
    tenant_id: str
    id: str
    cell_id: str
    mode: Literal["watcher", "claimer", "crawler"]
    status: Literal["healthy", "draining", "stale", "dead"]
    account_id: str | None
    contexts: int
    memory_mb: int
    cpu_pct: float
    heartbeat_age_s: float
    version: str
    started_at: str


class ClaimEvent(Wire):
    at: str
    state: ClaimState
    actor: str
    note: str | None = None


class Claim(Wire):
    tenant_id: str
    id: str
    target_job_key: str
    lane: str
    rate_usd: int
    state: ClaimState
    resolution: str | None
    result: str | None
    worker_id: str | None
    account_id: str | None
    fencing_token: int | None
    published_at: str | None  # boards that do not stamp a post time
    seen_at: str
    queued_at: str | None
    leased_at: str | None
    act_sent_at: str | None
    confirmed_at: str | None
    events: list[ClaimEvent]


class Account(Wire):
    tenant_id: str
    id: str
    label: str
    target: str
    enabled: bool
    session_state: Literal["fresh", "expiring", "expired", "otp_required"]
    session_expires_in_s: int
    session_ttl_s: int
    last_refresh_at: str | None
    otp_channel: Literal["email", "sms", "manual"]
    active_lease: str | None
    rate_limit_per_min: int


class Filter(Wire):
    tenant_id: str
    id: str
    name: str
    enabled: bool
    origin: str
    destination: str
    min_rate_usd: int
    equipment: list[str]
    max_weight_lb: int
    account_group: str
    matched_24h: int
    updated_at: str
    version: int


class ScheduleWindow(Wire):
    """Whole-hour span on the week grid. `day`: 0 = Monday ... 6 = Sunday (as the engine counts)."""

    day: int
    start_hour: int
    end_hour: int


class Schedule(Wire):
    tenant_id: str
    id: str
    name: str
    timezone: str
    targets: list[str]
    windows: list[ScheduleWindow]
    enabled: bool


class AuditEntry(Wire):
    tenant_id: str
    id: str
    at: str
    actor: str
    role: Literal["owner", "operator", "viewer", "demo", "system"]
    action: str
    target: str
    detail: str
    ip: str


class User(Wire):
    tenant_id: str
    id: str
    name: str
    email: str
    role: UserRole
    mfa: bool
    last_seen_at: str | None


class Cell(Wire):
    """Other tenants are only counted; `your_workers` counts the viewer's own tenant's workers."""

    id: str
    name: str
    region: str
    capacity: int
    tenant_count: int
    hosts_you: bool
    your_workers: int


class LatencyStage(Wire):
    key: Literal["publish_to_seen", "seen_to_queued", "queued_to_leased", "leased_to_act", "act_to_confirmed"]
    samples: int
    p50: int
    p95: int
    p99: int


class SeriesPoint(Wire):
    t: str
    v: int


class Alert(Wire):
    id: str
    severity: Literal["critical", "warning", "info"]
    kind: Literal["stale_workers", "sessions_need_attention", "claims_being_reconciled"]
    count: int


# ---------------- pages and envelopes ----------------


class WorkerPage(Wire):
    tenant_id: str
    items: list[Worker]
    next_cursor: str | None
    total_estimate: int


class ClaimPage(Wire):
    tenant_id: str
    items: list[Claim]
    next_cursor: str | None
    total_estimate: int


class AccountPage(Wire):
    tenant_id: str
    items: list[Account]
    next_cursor: str | None
    total_estimate: int


class FilterPage(Wire):
    tenant_id: str
    items: list[Filter]
    next_cursor: str | None
    total_estimate: int


class SchedulePage(Wire):
    tenant_id: str
    items: list[Schedule]
    next_cursor: str | None
    total_estimate: int


class AuditPage(Wire):
    tenant_id: str
    items: list[AuditEntry]
    next_cursor: str | None
    total_estimate: int


class UserPage(Wire):
    tenant_id: str
    items: list[User]
    next_cursor: str | None
    total_estimate: int


class CellList(Wire):
    items: list[Cell]


class Latency(Wire):
    tenant_id: str
    window_s: int
    stages: list[LatencyStage]


class ClaimSeries(Wire):
    total: list[SeriesPoint]
    confirmed: list[SeriesPoint]


class WorkerTotals(Wire):
    total: int
    healthy: int


class ClaimCounts(Wire):
    """Claims queued in the last `window_s` (the same window as the chart). `confirmed` includes
    claims the reconciler found booked; `finished` counts CONFIRMED, FAILED and RECONCILED."""

    window_s: int
    total: int
    confirmed: int
    finished: int
    by_state: dict[str, int]


class Overview(Wire):
    tenant_id: str
    claims: ClaimCounts
    series: ClaimSeries
    workers: WorkerTotals
    alerts: list[Alert]


class Tenant(Wire):
    id: str
    slug: str
    name: str


class DemoAccess(Wire):
    tenant: bool
    can_control: bool


class Session(Wire):
    authenticated: bool
    role: ViewerRole
    name: str | None
    email: str | None
    redacted: bool
    csrf: str | None
    csrf_header: str
    tenant: Tenant
    demo: DemoAccess


class Cap(Wire):
    max: float | None = None
    choices: list[str] | None = None


class DemoStatus(Wire):
    run_active: bool
    run_ends_in_s: int
    run_max_minutes: int
    reset_after_s: int
    feed_rate_per_min: float | None
    adversity: dict[str, float | str | None]
    caps: dict[str, Cap]


class LoginResult(Wire):
    mfa_required: bool


class MfaResult(Wire):
    role: ViewerRole
    csrf: str


class SignedOut(Wire):
    signed_out: bool


class DemoHint(Wire):
    email: str
    password: str
    code: str


class Accepted(Wire):
    accepted: bool
