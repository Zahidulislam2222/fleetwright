/**
 * The `/v1` wire contract as the console consumes it. The source of truth is
 * apps/coordinator/src/fw_coordinator/schemas.py (published as contracts/openapi.yaml); a test
 * (apps/coordinator/tests/test_contract.py) fails when these types and the models drift apart.
 * Display wording (stage labels, alert titles) is the console's own; the wire carries keys and numbers.
 * Every list is cursor-paginated and every tenant record carries tenant_id.
 */

export type TenantId = string;

export type Page<T> = {
  tenant_id: TenantId;
  items: T[];
  next_cursor: string | null;
  total_estimate: number;
};

export type WorkerMode = "watcher" | "claimer" | "crawler";
export type WorkerStatus = "healthy" | "draining" | "stale" | "dead";

export type Worker = {
  tenant_id: TenantId;
  id: string;
  cell_id: string;
  mode: WorkerMode;
  status: WorkerStatus;
  account_id: string | null;
  contexts: number;
  memory_mb: number;
  cpu_pct: number;
  heartbeat_age_s: number;
  version: string;
  started_at: string;
};

export type ClaimState = "DETECTED" | "QUEUED" | "LEASED" | "ACTING" | "CONFIRMED" | "FAILED" | "UNKNOWN" | "RECONCILED";

export type ClaimEvent = {
  at: string;
  state: ClaimState;
  actor: string;
  note?: string | null;
};

export type Claim = {
  tenant_id: TenantId;
  id: string;
  target_job_key: string;
  lane: string;
  rate_usd: number;
  state: ClaimState;
  resolution: string | null;
  result: string | null;
  worker_id: string | null;
  account_id: string | null;
  fencing_token: number | null;
  published_at: string | null;
  seen_at: string;
  queued_at: string | null;
  leased_at: string | null;
  act_sent_at: string | null;
  confirmed_at: string | null;
  events: ClaimEvent[];
};

export type SessionState = "fresh" | "expiring" | "expired" | "otp_required";

export type Account = {
  tenant_id: TenantId;
  id: string;
  label: string;
  target: string;
  enabled: boolean;
  session_state: SessionState;
  session_expires_in_s: number;
  session_ttl_s: number;
  last_refresh_at: string | null;
  otp_channel: "email" | "sms" | "manual";
  active_lease: string | null;
  rate_limit_per_min: number;
};

export type Filter = {
  tenant_id: TenantId;
  id: string;
  name: string;
  enabled: boolean;
  origin: string;
  destination: string;
  min_rate_usd: number;
  equipment: string[];
  max_weight_lb: number;
  account_group: string;
  matched_24h: number;
  updated_at: string;
  version: number;
};

/** Whole-hour span on the week grid. `day`: 0 = Monday … 6 = Sunday (as the engine counts). */
export type ScheduleWindow = {
  day: number;
  start_hour: number;
  end_hour: number;
};

export type Schedule = {
  tenant_id: TenantId;
  id: string;
  name: string;
  timezone: string;
  targets: string[];
  windows: ScheduleWindow[];
  enabled: boolean;
};

/** Roles a console user can hold. */
export type Role = "owner" | "operator" | "viewer" | "demo";
/** Who is looking: a signed-in role, or `public` for an anonymous visitor of the demo. */
export type ViewerRole = "public" | Role;

export type AuditEntry = {
  tenant_id: TenantId;
  id: string;
  at: string;
  actor: string;
  role: Role | "system";
  action: string;
  target: string;
  detail: string;
  ip: string;
};

export type User = {
  tenant_id: TenantId;
  id: string;
  name: string;
  email: string;
  role: Role;
  mfa: boolean;
  last_seen_at: string | null;
};

/** Other tenants are only counted; `your_workers` counts the viewer's own tenant's workers. */
export type Cell = {
  id: string;
  name: string;
  region: string;
  capacity: number;
  tenant_count: number;
  hosts_you: boolean;
  your_workers: number;
};

export type CellList = {
  items: Cell[];
};

export type LatencyKey = "publish_to_seen" | "seen_to_queued" | "queued_to_leased" | "leased_to_act" | "act_to_confirmed";

export type LatencyStage = {
  key: LatencyKey;
  samples: number;
  p50: number;
  p95: number;
  p99: number;
};

export type Latency = {
  tenant_id: TenantId;
  window_s: number;
  stages: LatencyStage[];
};

export type SeriesPoint = {
  t: string;
  v: number;
};

export type ClaimSeries = {
  total: SeriesPoint[];
  confirmed: SeriesPoint[];
};

export type AlertKind = "stale_workers" | "sessions_need_attention" | "claims_being_reconciled";

export type Alert = {
  id: string;
  severity: "critical" | "warning" | "info";
  kind: AlertKind;
  count: number;
};

export type WorkerTotals = {
  total: number;
  healthy: number;
};

/** Claims queued in the last `window_s` (the chart's window); `finished` = CONFIRMED + FAILED + RECONCILED. */
export type ClaimCounts = {
  window_s: number;
  total: number;
  confirmed: number;
  finished: number;
  by_state: Record<string, number>;
};

export type Overview = {
  tenant_id: TenantId;
  claims: ClaimCounts;
  series: ClaimSeries;
  workers: WorkerTotals;
  alerts: Alert[];
};

export type Tenant = {
  id: string;
  slug: string;
  name: string;
};

export type DemoAccess = {
  tenant: boolean;
  can_control: boolean;
};

export type Session = {
  authenticated: boolean;
  role: ViewerRole;
  name: string | null;
  email: string | null;
  redacted: boolean;
  csrf: string | null;
  csrf_header: string;
  tenant: Tenant;
  demo: DemoAccess;
};

export type Cap = {
  max?: number | null;
  choices?: string[] | null;
};

export type DemoStatus = {
  run_active: boolean;
  run_ends_in_s: number;
  run_max_minutes: number;
  reset_after_s: number;
  feed_rate_per_min: number | null;
  adversity: Record<string, number | string | null>;
  caps: Record<string, Cap>;
};

export type LoginResult = {
  mfa_required: boolean;
};

export type MfaResult = {
  role: ViewerRole;
  csrf: string;
};

export type SignedOut = {
  signed_out: boolean;
};

export type DemoHint = {
  email: string;
  password: string;
  code: string;
};

export type Accepted = {
  accepted: boolean;
};

// ---------------- prototype only: the crawler is designed but not built ----------------

export type CrawlStatus = "running" | "succeeded" | "failed" | "alarm" | "queued";

export type CrawlJob = {
  tenant_id: TenantId;
  id: string;
  name: string;
  status: CrawlStatus;
  seeds: number;
  items_last_cycle: number;
  items_series: number[];
  new_items: number;
  changed_items: number;
  removed_items: number;
  retries: number;
  dlq: number;
  last_run_at: string;
  next_run_at: string;
  personal_data: boolean;
  robots_policy: "respect" | "ignore-with-authorisation";
  alarm: string | null;
};
