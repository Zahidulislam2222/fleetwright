/**
 * Shapes the console prototype consumes. They mirror the planned contract (contracts/openapi.yaml,
 * Phase 1 exit item): every list is cursor-paginated and every record carries tenant_id.
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

export type ClaimEvent = { at: string; state: ClaimState; actor: string; note?: string };

export type Claim = {
  tenant_id: TenantId;
  id: string;
  target_job_key: string;
  lane: string;
  rate_usd: number;
  state: ClaimState;
  worker_id: string | null;
  account_id: string | null;
  fencing_token: number | null;
  published_at: string;
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
  session_state: SessionState;
  session_expires_in_s: number;
  session_ttl_s: number;
  last_refresh_at: string;
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

export type ScheduleWindow = { day: number; start_hour: number; end_hour: number };

export type Schedule = {
  tenant_id: TenantId;
  id: string;
  name: string;
  timezone: string;
  targets: string[];
  windows: ScheduleWindow[];
  enabled: boolean;
};

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

export type AuditEntry = {
  tenant_id: TenantId;
  id: string;
  at: string;
  actor: string;
  role: Role;
  action: string;
  target: string;
  detail: string;
  ip: string;
};

export type Role = "owner" | "operator" | "viewer";

export type User = {
  tenant_id: TenantId;
  id: string;
  name: string;
  email: string;
  role: Role;
  mfa: boolean;
  last_seen_at: string;
};

export type Cell = {
  id: string;
  name: string;
  region: string;
  status: "healthy" | "degraded" | "offline";
  workers: number;
  capacity: number;
  tenants: TenantId[];
  claims_per_min: number;
  redis_lag_ms: number;
};

export type LatencyStage = {
  key: "publish_to_seen" | "seen_to_queued" | "queued_to_leased" | "leased_to_act" | "act_to_confirmed";
  label: string;
  p50: number;
  p95: number;
  p99: number;
};

export type Alert = {
  id: string;
  severity: "critical" | "warning" | "info";
  title: string;
  detail: string;
  at: string;
};

export type SeriesPoint = { t: string; v: number };
