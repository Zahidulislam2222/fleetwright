"use client";

import { CircleAlert, CircleCheck, CircleDashed, CircleX, Inbox, Loader, Lock, OctagonAlert, RefreshCw, TriangleAlert, type LucideIcon } from "lucide-react";
import copy from "@/content/console.json";
import { usePrototype } from "./prototypeStore";

/* ─── Page header ─────────────────────────────────────────────────── */

export function PageHeader({ title, description, actions }: { title: string; description: string; actions?: React.ReactNode }) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div className="min-w-0">
        <h1 className="text-[clamp(22px,2.4vw,28px)] font-semibold tracking-[-0.02em] text-c-text">{title}</h1>
        <p className="mt-1 max-w-[68ch] text-[14.5px] leading-relaxed text-c-text-2">{description}</p>
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Panel({ title, aside, children, className = "" }: { title?: string; aside?: React.ReactNode; children: React.ReactNode; className?: string }) {
  return (
    <section className={`min-w-0 rounded-2xl border border-c-border bg-c-surface shadow-[var(--c-shadow)] ${className}`}>
      {title && (
        <div className="flex flex-wrap items-center justify-between gap-2 border-b border-c-border px-4 py-3 sm:px-5">
          <h2 className="text-[14.5px] font-semibold text-c-text">{title}</h2>
          {aside}
        </div>
      )}
      {children}
    </section>
  );
}

/* ─── Status: always icon + label, never colour alone ─────────────── */

export type Tone = "ok" | "warn" | "bad" | "info" | "neutral";

const toneClass: Record<Tone, string> = {
  ok: "bg-c-ok-bg text-c-ok",
  warn: "bg-c-warn-bg text-c-warn",
  bad: "bg-c-bad-bg text-c-bad",
  info: "bg-c-info-bg text-c-info",
  neutral: "bg-c-surface-3 text-c-text-2",
};

const toneIcon: Record<Tone, LucideIcon> = {
  ok: CircleCheck,
  warn: TriangleAlert,
  bad: CircleX,
  info: CircleAlert,
  neutral: CircleDashed,
};

export function Badge({ tone, children, icon }: { tone: Tone; children: React.ReactNode; icon?: LucideIcon }) {
  const Icon = icon ?? toneIcon[tone];
  return (
    <span className={`inline-flex shrink-0 items-center gap-1 whitespace-nowrap rounded-full px-2 py-0.5 text-[12px] font-medium ${toneClass[tone]}`}>
      <Icon aria-hidden className="size-3.5" />
      {children}
    </span>
  );
}

export const workerTone = { healthy: "ok", draining: "info", stale: "warn", dead: "bad" } as const;
export const claimTone = { DETECTED: "neutral", QUEUED: "neutral", LEASED: "info", ACTING: "info", CONFIRMED: "ok", FAILED: "bad", UNKNOWN: "warn", RECONCILED: "ok" } as const;
export const sessionTone = { fresh: "ok", expiring: "warn", expired: "bad", otp_required: "warn" } as const;
export const crawlTone = { running: "info", succeeded: "ok", failed: "bad", alarm: "warn", queued: "neutral" } as const;

/* ─── Buttons ─────────────────────────────────────────────────────── */

export function Button({ variant = "secondary", className = "", ...props }: React.ButtonHTMLAttributes<HTMLButtonElement> & { variant?: "primary" | "secondary" | "ghost" }) {
  const v =
    variant === "primary"
      ? "bg-c-text text-c-bg hover:opacity-90"
      : variant === "ghost"
        ? "text-c-text-2 hover:bg-c-surface-2 hover:text-c-text"
        : "border border-c-border bg-c-surface text-c-text hover:bg-c-surface-2";
  return (
    <button
      {...props}
      className={`inline-flex h-9 items-center justify-center gap-2 rounded-lg px-3.5 text-[13.5px] font-medium transition-colors duration-150 disabled:cursor-not-allowed disabled:opacity-50 aria-disabled:cursor-not-allowed aria-disabled:opacity-50 ${v} ${className}`}
    />
  );
}

/* ─── Data states ─────────────────────────────────────────────────── */

type StateCopy = { title: string; body: string };

function StatePanel({ icon: Icon, tone, title, body, action }: { icon: LucideIcon; tone: Tone; title: string; body: string; action?: React.ReactNode }) {
  return (
    <div className="grid place-items-center rounded-2xl border border-dashed border-c-border-strong bg-c-surface px-6 py-16 text-center">
      <span className={`grid size-11 place-items-center rounded-full ${toneClass[tone]}`}>
        <Icon aria-hidden className="size-5" />
      </span>
      <h2 className="mt-4 text-[16px] font-semibold text-c-text">{title}</h2>
      <p className="mt-1.5 max-w-[46ch] text-[14px] leading-relaxed text-c-text-2">{body}</p>
      {action && <div className="mt-5">{action}</div>}
    </div>
  );
}

export function Skeleton({ rows = 6 }: { rows?: number }) {
  return (
    <div role="status" aria-live="polite" className="rounded-2xl border border-c-border bg-c-surface p-4">
      <span className="sr-only">{copy.common.loading}…</span>
      <div className="mb-4 flex items-center gap-2 text-[13px] text-c-text-3">
        <Loader aria-hidden className="size-4 animate-spin" /> {copy.common.loading}
      </div>
      <div className="space-y-3" aria-hidden>
        {Array.from({ length: rows }, (_, i) => (
          <div key={i} className="h-9 animate-pulse rounded-lg bg-c-surface-2" style={{ animationDelay: `${i * 80}ms` }} />
        ))}
      </div>
    </div>
  );
}

/** Renders the prototype-selected state; children render only when "ready". */
export function DataState({ copy: c, rows, children }: { copy: { empty: StateCopy; error: StateCopy; denied: StateCopy }; rows?: number; children: React.ReactNode }) {
  const { state, setState } = usePrototype();
  if (state === "loading") return <Skeleton rows={rows} />;
  if (state === "empty") return <StatePanel icon={Inbox} tone="neutral" {...c.empty} />;
  if (state === "error")
    return (
      <div role="alert">
        <StatePanel
          icon={OctagonAlert}
          tone="bad"
          {...c.error}
          action={
            <Button onClick={() => setState("ready")}>
              <RefreshCw aria-hidden className="size-4" /> {copy.common.retry}
            </Button>
          }
        />
      </div>
    );
  if (state === "denied")
    return <StatePanel icon={Lock} tone="warn" {...c.denied} action={<Button disabled title={copy.common.prototypeOnly}>{copy.common.requestAccess}</Button>} />;
  return <>{children}</>;
}

/* ─── Mock label ──────────────────────────────────────────────────── */

export function MockTag() {
  return <span className="rounded-md border border-c-border px-1.5 py-0.5 font-mono text-[10.5px] uppercase tracking-[0.12em] text-c-text-3">{copy.common.mock}</span>;
}
