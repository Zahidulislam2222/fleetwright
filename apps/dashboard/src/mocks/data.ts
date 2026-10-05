/**
 * Deterministic mock data for the console prototype. Everything is derived from seed.json with a
 * seeded PRNG and a fixed "as of" instant, so server and client render identical markup.
 * All values are MOCK DATA — none of it is a measurement.
 */
import seed from "./seed.json";
import { fill } from "@/lib/fill";
import type {
  Account,
  Alert,
  AuditEntry,
  Cell,
  Claim,
  ClaimEvent,
  ClaimState,
  CrawlJob,
  CrawlStatus,
  Filter,
  LatencyStage,
  Page,
  Role,
  Schedule,
  SeriesPoint,
  SessionState,
  TenantId,
  User,
  Worker,
  WorkerMode,
  WorkerStatus,
} from "./types";

export const AS_OF = Date.parse(seed.asOf);
const N = seed.eventNotes;
export const tenants = seed.tenants;
export const target = seed.target;

function mulberry32(a: number) {
  return () => {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function hashString(s: string) {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) h = Math.imul(h ^ s.charCodeAt(i), 16777619);
  return h >>> 0;
}

/** Independent stream per dataset + tenant, so adding one dataset never reshuffles another. */
function rng(name: string) {
  return mulberry32(seed.seed ^ hashString(name));
}

function pickWeighted<K extends string>(rand: () => number, weights: Record<K, number>): K {
  const entries = Object.entries(weights) as [K, number][];
  let r = rand() * entries.reduce((s, [, w]) => s + w, 0);
  for (const [k, w] of entries) {
    r -= w;
    if (r <= 0) return k;
  }
  return entries[entries.length - 1][0];
}

const between = (rand: () => number, [lo, hi]: number[]) => Math.round(lo + rand() * (hi - lo));
const iso = (ms: number) => new Date(ms).toISOString();
const pick = <T,>(rand: () => number, list: readonly T[]) => list[Math.floor(rand() * list.length)];
const pad = (n: number, w = 3) => String(n).padStart(w, "0");

const tenantOf = (id: TenantId) => {
  const t = seed.tenants.find((x) => x.id === id);
  if (!t) throw new Error(`Unknown tenant ${id}`);
  return t;
};

/* ─── Datasets (memoised per tenant) ──────────────────────────────── */

const memo = new Map<string, unknown>();
function cached<T>(key: string, build: () => T): T {
  if (!memo.has(key)) memo.set(key, build());
  return memo.get(key) as T;
}

export function accounts(tenant: TenantId): Account[] {
  return cached(`accounts:${tenant}`, () => {
    const t = tenantOf(tenant);
    const rand = rng(`accounts:${tenant}`);
    return Array.from({ length: t.accounts }, (_, i) => {
      const ttl = 8 * 3600;
      const r = rand();
      const state: SessionState = r < 0.72 ? "fresh" : r < 0.86 ? "expiring" : r < 0.94 ? "otp_required" : "expired";
      const expiresIn = state === "fresh" ? between(rand, [5400, ttl]) : state === "expiring" ? between(rand, [120, 1500]) : 0;
      return {
        tenant_id: tenant,
        id: `${tenant}-acct-${pad(i + 1, 2)}`,
        label: `${t.name.split(" ")[0]} dispatch ${i + 1}`,
        target: seed.target.name,
        session_state: state,
        session_expires_in_s: expiresIn,
        session_ttl_s: ttl,
        last_refresh_at: iso(AS_OF - between(rand, [60, ttl]) * 1000),
        otp_channel: pick(rand, ["email", "email", "sms", "manual"] as const),
        active_lease: null,
        rate_limit_per_min: pick(rand, [6, 10, 12]),
      };
    });
  });
}

export function workers(tenant: TenantId): Worker[] {
  return cached(`workers:${tenant}`, () => {
    const t = tenantOf(tenant);
    const rand = rng(`workers:${tenant}`);
    const accts = accounts(tenant);
    return Array.from({ length: t.workers }, (_, i) => {
      const mode = pickWeighted(rand, seed.workerModes) as WorkerMode;
      const status = pickWeighted(rand, seed.workerStatus) as WorkerStatus;
      const heartbeat = status === "healthy" ? between(rand, [1, 9]) : status === "draining" ? between(rand, [2, 12]) : status === "stale" ? between(rand, [45, 160]) : between(rand, [600, 3600]);
      return {
        tenant_id: tenant,
        id: `w-${tenant.slice(2, 4)}${pad(i + 1, 2)}`,
        cell_id: t.cell,
        mode,
        status,
        account_id: mode === "claimer" ? accts[i % accts.length].id : null,
        contexts: mode === "crawler" ? between(rand, [2, 6]) : 1,
        memory_mb: status === "dead" ? 0 : between(rand, [180, 520]),
        cpu_pct: status === "dead" ? 0 : between(rand, [3, 46]),
        heartbeat_age_s: heartbeat,
        version: pick(rand, seed.workerVersions),
        started_at: iso(AS_OF - between(rand, [1800, 86400 * 3]) * 1000),
      };
    });
  });
}

const STAGES = ["publish_to_seen", "seen_to_queued", "queued_to_leased", "leased_to_act", "act_to_confirmed"] as const;
const ORDER: ClaimState[] = ["DETECTED", "QUEUED", "LEASED", "ACTING", "CONFIRMED"];

export function claims(tenant: TenantId): Claim[] {
  return cached(`claims:${tenant}`, () => {
    const t = tenantOf(tenant);
    const rand = rng(`claims:${tenant}`);
    const ws = workers(tenant).filter((w) => w.mode === "claimer" && w.status !== "dead");
    const count = t.claimsPerHour;
    let fence = 4100 + Math.floor(rand() * 900);
    // Job keys are unique per tenant: the board never publishes the same load twice, and the
    // product invariant (one confirmation per job) must hold in the mock data too.
    let jobKey = 48000 + Math.floor(rand() * 400);
    const list: Claim[] = [];
    for (let i = 0; i < count; i++) {
      let state = pickWeighted(rand, seed.claimStates) as ClaimState;
      const published = AS_OF - Math.floor(((count - i) / count) * 3600_000) + between(rand, [0, 9000]);
      const d = STAGES.map((s) => between(rand, seed.stageMs[s]));
      const seen = published + d[0];
      const queued = seen + d[1];
      const leased = queued + d[2];
      const act = leased + d[3];
      const done = act + d[4];
      const reached = state === "FAILED" || state === "UNKNOWN" || state === "RECONCILED" ? 3 : ORDER.indexOf(state);
      const w = pick(rand, ws);
      const losers = between(rand, [2, 11]);
      const events: ClaimEvent[] = [
        { at: iso(seen), state: "DETECTED", actor: fill(N.watcherActor, { cell: w.cell_id }) },
        { at: iso(queued), state: "QUEUED", actor: N.coordinatorActor, note: fill(N.notified, { n: losers + 1 }) },
      ];
      if (reached >= 2) events.push({ at: iso(leased), state: "LEASED", actor: w.id, note: fill(N.wonLease, { n: losers }) });
      if (reached >= 3) events.push({ at: iso(act), state: "ACTING", actor: w.id, note: fill(N.fencing, { token: fence + 1 }) });
      if (state === "CONFIRMED") events.push({ at: iso(done), state: "CONFIRMED", actor: N.boardActor, note: N.confirmed });
      if (state === "FAILED") events.push({ at: iso(done), state: "FAILED", actor: N.boardActor, note: pick(rand, N.failed) });
      if (state === "UNKNOWN" || state === "RECONCILED") events.push({ at: iso(done), state: "UNKNOWN", actor: w.id, note: N.lost });
      if (state === "RECONCILED") {
        // The reconciler resolves UNKNOWN against the board: found → confirmed; not found → released (a failure, not a booking).
        const found = rand() < 0.6;
        events.push({ at: iso(done + 41_000), state: found ? "RECONCILED" : "FAILED", actor: N.reconcilerActor, note: found ? N.reconciledFound : N.reconciledReleased });
        if (!found) state = "FAILED";
      }
      if (reached >= 2) fence++;
      const o = pick(rand, seed.cities);
      let dest = pick(rand, seed.cities);
      if (dest === o) dest = seed.cities[(seed.cities.indexOf(o) + 3) % seed.cities.length];
      list.push({
        tenant_id: tenant,
        id: `cl-${tenant.slice(2, 4)}${pad(i + 1, 4)}`,
        target_job_key: `LD-${(jobKey += 1 + Math.floor(rand() * 9))}`,
        lane: `${o} → ${dest}`,
        rate_usd: between(rand, [1200, 3600]),
        state,
        worker_id: reached >= 2 ? w.id : null,
        account_id: reached >= 2 ? w.account_id : null,
        fencing_token: reached >= 2 ? fence : null,
        published_at: iso(published),
        seen_at: iso(seen),
        queued_at: iso(queued),
        leased_at: reached >= 2 ? iso(leased) : null,
        act_sent_at: reached >= 3 ? iso(act) : null,
        confirmed_at: state === "CONFIRMED" ? iso(done) : null,
        events,
      });
    }
    return list.reverse();
  });
}

export function filters(tenant: TenantId): Filter[] {
  return cached(`filters:${tenant}`, () => {
    const rand = rng(`filters:${tenant}`);
    return seed.filters.map((f, i) => ({
      tenant_id: tenant,
      id: `${tenant}-flt-${i + 1}`,
      ...f,
      enabled: rand() > 0.2,
      account_group: pick(rand, ["all accounts", "dispatch pool A", "dispatch pool B"]),
      matched_24h: between(rand, [0, 140]),
      updated_at: iso(AS_OF - between(rand, [3600, 86400 * 9]) * 1000),
      version: between(rand, [1, 14]),
    }));
  });
}

export function schedules(tenant: TenantId): Schedule[] {
  return cached(`schedules:${tenant}`, () =>
    seed.schedules.map((s, i) => ({
      tenant_id: tenant,
      id: `${tenant}-sch-${i + 1}`,
      name: s.name,
      timezone: s.timezone,
      targets: [seed.target.name],
      windows: s.windows.map(([day, start_hour, end_hour]) => ({ day, start_hour, end_hour })),
      enabled: i !== 1,
    })),
  );
}

export function crawlJobs(tenant: TenantId): CrawlJob[] {
  return cached(`crawl:${tenant}`, () => {
    const rand = rng(`crawl:${tenant}`);
    return seed.crawlJobs.map((c, i) => {
      const series = Array.from({ length: 12 }, () => Math.round(c.base * (0.9 + rand() * 0.2)));
      if (c.status === "alarm") series[11] = c.alarm?.startsWith("Zero") ? 0 : Math.round(c.base * 0.38);
      return {
        tenant_id: tenant,
        id: `${tenant}-crawl-${i + 1}`,
        name: c.name,
        status: c.status as CrawlStatus,
        seeds: c.seeds,
        items_last_cycle: series[11],
        items_series: series,
        new_items: between(rand, [0, 40]),
        changed_items: between(rand, [0, 60]),
        removed_items: between(rand, [0, 12]),
        retries: between(rand, [0, 9]),
        dlq: c.status === "failed" ? between(rand, [3, 12]) : between(rand, [0, 1]),
        last_run_at: iso(AS_OF - between(rand, [300, 7200]) * 1000),
        next_run_at: iso(AS_OF + between(rand, [300, 7200]) * 1000),
        personal_data: c.name === "carrier-directory",
        robots_policy: "respect",
        alarm: c.alarm,
      };
    });
  });
}

export function users(tenant: TenantId): User[] {
  return cached(`users:${tenant}`, () => {
    const rand = rng(`users:${tenant}`);
    return seed.operators.map((u) => ({
      tenant_id: tenant,
      id: u.id,
      name: u.name,
      email: `${u.emailLocal}@${fill(seed.emailDomain, { tenant: tenant.replace(/^t-/, "") })}`,
      role: u.role as Role,
      mfa: true, // the tenant policy requires TOTP for every user
      last_seen_at: iso(AS_OF - between(rand, [60, 86400 * 4]) * 1000),
    }));
  });
}

export function audit(tenant: TenantId): AuditEntry[] {
  return cached(`audit:${tenant}`, () => {
    const rand = rng(`audit:${tenant}`);
    const us = users(tenant);
    const ws = workers(tenant);
    return Array.from({ length: 180 }, (_, i) => {
      const a = pick(rand, seed.auditActions);
      const u = pick(rand, us.filter((x) => x.role !== "viewer" || a.action === "user.login"));
      const target =
        a.target === "filter" ? pick(rand, filters(tenant)).name
        : a.target === "worker" ? pick(rand, ws).id
        : a.target === "account" ? pick(rand, accounts(tenant)).id
        : a.target === "claim" ? pick(rand, claims(tenant)).id
        : a.target === "schedule" ? pick(rand, schedules(tenant)).name
        : a.target === "crawl" ? pick(rand, seed.crawlJobs).name
        : a.target;
      return {
        tenant_id: tenant,
        id: `au-${pad(180 - i, 4)}`,
        at: iso(AS_OF - (i * 41 + between(rand, [0, 30])) * 60_000 / 6),
        actor: a.action === "claim.reconcile" ? "reconciler (system)" : u.name,
        role: u.role,
        action: a.action,
        target,
        detail: a.detail,
        ip: `10.0.${between(rand, [1, 4])}.${between(rand, [10, 250])}`,
      };
    });
  });
}

export function cells(): Cell[] {
  return cached("cells", () =>
    seed.cells.map((c) => {
      const ts = seed.tenants.filter((t) => t.cell === c.id);
      const ws = ts.flatMap((t) => workers(t.id));
      return {
        id: c.id,
        name: c.name,
        region: c.region,
        status: ws.some((w) => w.status === "dead") ? "degraded" : "healthy",
        workers: ws.filter((w) => w.status !== "dead").length,
        capacity: c.capacity,
        tenants: ts.map((t) => t.id),
        claims_per_min: Math.round(ts.reduce((s, t) => s + t.claimsPerHour, 0) / 60),
        redis_lag_ms: between(rng(`cell:${c.id}`), [1, 7]),
      };
    }),
  );
}

/* ─── Derived views ───────────────────────────────────────────────── */

function percentile(sorted: number[], p: number) {
  if (sorted.length === 0) return 0;
  const idx = Math.min(sorted.length - 1, Math.max(0, Math.ceil((p / 100) * sorted.length) - 1));
  return sorted[idx];
}

const STAGE_FIELDS: Record<LatencyStage["key"], [keyof Claim, keyof Claim]> = {
  publish_to_seen: ["published_at", "seen_at"],
  seen_to_queued: ["seen_at", "queued_at"],
  queued_to_leased: ["queued_at", "leased_at"],
  leased_to_act: ["leased_at", "act_sent_at"],
  act_to_confirmed: ["act_sent_at", "confirmed_at"],
};

/** Percentiles computed from the mock claims' own timestamps (nearest-rank). */
export function latency(tenant: TenantId, labels: Record<LatencyStage["key"], string>): LatencyStage[] {
  const list = claims(tenant);
  return STAGES.map((key) => {
    const [from, to] = STAGE_FIELDS[key];
    const values = list
      .filter((c) => c[from] && c[to])
      .map((c) => Date.parse(c[to] as string) - Date.parse(c[from] as string))
      .sort((a, b) => a - b);
    return { key, label: labels[key], p50: percentile(values, 50), p95: percentile(values, 95), p99: percentile(values, 99) };
  });
}

/** Claims bucketed per 5 minutes over the last hour. */
export function claimSeries(tenant: TenantId): { confirmed: SeriesPoint[]; total: SeriesPoint[] } {
  const bucket = 5 * 60_000;
  const start = AS_OF - 3600_000;
  const n = 12;
  const total = Array.from({ length: n }, (_, i) => ({ t: iso(start + (i + 1) * bucket), v: 0 }));
  const confirmed = total.map((p) => ({ ...p }));
  for (const c of claims(tenant)) {
    const i = Math.min(n - 1, Math.max(0, Math.floor((Date.parse(c.published_at) - start) / bucket)));
    total[i].v++;
    if (c.state === "CONFIRMED" || c.state === "RECONCILED") confirmed[i].v++;
  }
  return { confirmed, total };
}

export function alerts(tenant: TenantId, copy: { staleWorkers: string; expiring: string; crawlAlarm: string }): Alert[] {
  const out: Alert[] = [];
  const stale = workers(tenant).filter((w) => w.status === "stale" || w.status === "dead");
  if (stale.length) out.push({ id: "a-workers", severity: "critical", title: fill(copy.staleWorkers, { n: stale.length }), detail: stale.map((w) => w.id).join(", "), at: seed.asOf });
  const exp = accounts(tenant).filter((a) => a.session_state !== "fresh");
  if (exp.length) out.push({ id: "a-sessions", severity: "warning", title: fill(copy.expiring, { n: exp.length }), detail: exp.map((a) => a.label).join(", "), at: seed.asOf });
  for (const c of crawlJobs(tenant).filter((j) => j.alarm)) {
    out.push({ id: `a-${c.id}`, severity: "warning", title: fill(copy.crawlAlarm, { name: c.name }), detail: c.alarm ?? "", at: c.last_run_at });
  }
  return out;
}

/* ─── Cursor pagination (mirrors the planned API shape) ───────────── */

const encode = (offset: number) => `c_${offset.toString(36)}`;
const decode = (cursor: string | null) => (cursor && /^c_[0-9a-z]+$/.test(cursor) ? parseInt(cursor.slice(2), 36) : 0);

export function paginate<T>(tenant: TenantId, items: T[], cursor: string | null, limit = seed.pageSize): Page<T> {
  const offset = decode(cursor);
  const slice = items.slice(offset, offset + limit);
  const next = offset + limit < items.length ? encode(offset + limit) : null;
  return { tenant_id: tenant, items: slice, next_cursor: next, total_estimate: items.length };
}

/* ─── Formatting against the fixed mock clock ─────────────────────── */

const timeFmt = new Intl.DateTimeFormat("en-GB", { hour: "2-digit", minute: "2-digit", second: "2-digit", timeZone: seed.displayTimeZone, hour12: false });
const dateTimeFmt = new Intl.DateTimeFormat("en-GB", { day: "2-digit", month: "short", hour: "2-digit", minute: "2-digit", timeZone: seed.displayTimeZone, hour12: false });

export const fmtTime = (isoStr: string) => timeFmt.format(new Date(isoStr));
export const fmtDateTime = (isoStr: string) => `${dateTimeFmt.format(new Date(isoStr))} ${seed.displayTimeZone}`;
export const tz = seed.displayTimeZone;

export function fmtAgo(isoStr: string) {
  const s = Math.round((AS_OF - Date.parse(isoStr)) / 1000);
  if (s < 0) return `in ${fmtDuration(-s)}`;
  return `${fmtDuration(s)} ago`;
}

export function fmtDuration(s: number) {
  if (s < 60) return `${s}s`;
  if (s < 3600) return `${Math.floor(s / 60)}m`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ${Math.floor((s % 3600) / 60)}m`;
  return `${Math.floor(s / 86400)}d`;
}

export const fmtMs = (ms: number) => (ms >= 1000 ? `${(ms / 1000).toFixed(2)} s` : `${ms} ms`);
export const fmtUsd = (v: number) => `$${v.toLocaleString("en-US")}`;

/* ─── Mock load board feed ────────────────────────────────────────── */

export type BoardLoad = { id: string; lane: string; equipment: string; weight_lb: number; rate_usd: number; posted_at: string; contested: boolean };

/** Loads on the fictitious board. "contested" loads are booked by someone else first when you try. */
export function boardLoads(): BoardLoad[] {
  return cached("board", () => {
    const rand = rng("board");
    let key = 49120;
    return Array.from({ length: 14 }, (_, i) => {
      const o = pick(rand, seed.cities);
      let d = pick(rand, seed.cities);
      if (d === o) d = seed.cities[(seed.cities.indexOf(o) + 5) % seed.cities.length];
      return {
        id: `LD-${(key += 1 + Math.floor(rand() * 7))}`,
        lane: `${o} → ${d}`,
        equipment: pick(rand, seed.equipment),
        weight_lb: between(rand, [18000, 44000]),
        rate_usd: between(rand, [1100, 3800]),
        posted_at: iso(AS_OF - (i * 47 + between(rand, [3, 40])) * 1000),
        contested: i === 1 || i === 6,
      };
    });
  });
}
