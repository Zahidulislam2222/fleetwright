"use client";

import Link from "next/link";
import { useMemo } from "react";
import { ArrowUpRight, OctagonAlert, TriangleAlert } from "lucide-react";
import { alerts, cells, claims, claimSeries, fmtAgo, fmtTime, tenants, tz, workers } from "@/mocks/data";
import copy from "@/content/console.json";
import { usePrototype } from "../prototypeStore";
import { Badge, claimTone, DataState, MockTag, PageHeader, Panel } from "../ui";
import { LineChart } from "../charts";
import { fill } from "@/lib/fill";

const p = copy.pages.overview;

function Tile({ label, value, note }: { label: string; value: string; note?: string }) {
  return (
    <div className="rounded-2xl border border-c-border bg-c-surface p-4 shadow-[var(--c-shadow)] sm:p-5">
      <p className="text-[13px] text-c-text-2">{label}</p>
      <p className="mt-2 text-[30px] font-semibold leading-none tracking-[-0.02em] text-c-text">{value}</p>
      {note && <p className="mt-2 text-[12.5px] text-c-text-3">{note}</p>}
    </div>
  );
}

export function OverviewView() {
  const { tenant } = usePrototype();
  const data = useMemo(() => {
    const ws = workers(tenant);
    const cs = claims(tenant);
    const done = cs.filter((c) => c.state === "CONFIRMED" || c.state === "RECONCILED").length;
    const terminal = cs.filter((c) => ["CONFIRMED", "RECONCILED", "FAILED", "UNKNOWN"].includes(c.state)).length;
    const keys = new Set<string>();
    let duplicates = 0;
    for (const c of cs) {
      if (c.state !== "CONFIRMED") continue;
      if (keys.has(c.target_job_key)) duplicates++;
      keys.add(c.target_job_key);
    }
    return {
      live: ws.filter((w) => w.status === "healthy" || w.status === "draining").length,
      total: ws.length,
      claims: cs.length,
      rate: terminal ? Math.round((done / terminal) * 1000) / 10 : 0,
      duplicates,
      series: claimSeries(tenant),
      alerts: alerts(tenant, p.alerts),
      recent: cs.slice(0, 6),
    };
  }, [tenant]);
  const tenantName = tenants.find((t) => t.id === tenant)?.name ?? tenant;

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p} rows={8}>
        <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
          <Tile label={p.tiles.workers} value={`${data.live}/${data.total}`} />
          <Tile label={p.tiles.claims} value={String(data.claims)} />
          <Tile label={p.tiles.confirmRate} value={fill(copy.common.percent, { n: data.rate })} />
          <Tile label={p.tiles.duplicates} value={String(data.duplicates)} note={p.duplicatesNote} />
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[minmax(0,1fr)_380px]">
          <Panel title={p.chartTitle} aside={<span className="text-[12px] text-c-text-3">{tenantName} · {tz}</span>}>
            <div className="p-4 sm:p-5">
              <LineChart
                title={`${p.chartTitle}, ${tenantName}`}
                xLabels={data.series.total.map((pt) => fmtTime(pt.t).slice(0, 5))}
                series={[
                  { id: "total", label: p.chartSeries.total, color: "var(--c-series-1)", points: data.series.total.map((pt) => pt.v) },
                  { id: "confirmed", label: p.chartSeries.confirmed, color: "var(--c-series-2)", points: data.series.confirmed.map((pt) => pt.v) },
                ]}
              />
            </div>
          </Panel>

          <Panel title={p.alertsTitle}>
            <ul className="divide-y divide-c-border">
              {data.alerts.map((a) => (
                <li key={a.id} className="flex gap-3 px-4 py-3 sm:px-5">
                  {a.severity === "critical" ? (
                    <OctagonAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-c-bad" />
                  ) : (
                    <TriangleAlert aria-hidden className="mt-0.5 size-4 shrink-0 text-c-warn" />
                  )}
                  <div className="min-w-0">
                    <p className="text-[13.5px] font-medium text-c-text">
                      <span className="sr-only">{a.severity}: </span>
                      {a.title}
                    </p>
                    <p className="mt-0.5 truncate text-[12.5px] text-c-text-2" title={a.detail}>{a.detail}</p>
                  </div>
                </li>
              ))}
            </ul>
          </Panel>
        </div>

        <div className="mt-4 grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
          <Panel title={p.cellsTitle}>
            <ul className="divide-y divide-c-border">
              {cells().map((c) => (
                <li key={c.id} className="px-4 py-3.5 sm:px-5">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-c-text">{c.name} <span className="font-normal text-c-text-3">· {c.region}</span></p>
                    <Badge tone={c.status === "healthy" ? "ok" : c.status === "degraded" ? "warn" : "bad"}>{copy.status[c.status]}</Badge>
                  </div>
                  <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-c-surface-3" aria-hidden>
                    <div className="h-full rounded-full bg-c-text-2" style={{ width: `${(c.workers / c.capacity) * 100}%` }} />
                  </div>
                  <p className="mt-2 text-[12.5px] text-c-text-2 tabular">
                    {fill(p.cellLine, { workers: c.workers, capacity: c.capacity, cpm: c.claims_per_min, lag: c.redis_lag_ms, tenants: c.tenants.length })}
                  </p>
                </li>
              ))}
            </ul>
          </Panel>

          <Panel
            title={p.recentTitle}
            aside={
              <Link href="/console/claims" className="inline-flex items-center gap-1 rounded text-[13px] text-c-accent-text hover:underline">
                {copy.nav.find((n) => n.href === "/console/claims")?.label} <ArrowUpRight aria-hidden className="size-3.5" />
              </Link>
            }
          >
            <ul className="divide-y divide-c-border">
              {data.recent.map((c) => (
                <li key={c.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 sm:px-5">
                  <span className="w-[86px] font-mono text-[12.5px] text-c-text">{c.target_job_key}</span>
                  <Badge tone={claimTone[c.state]}>{copy.claimStates[c.state]}</Badge>
                  <span className="min-w-0 flex-1 truncate text-[13px] text-c-text-2">{c.lane}</span>
                  <span className="text-[12.5px] text-c-text-3 tabular">{fmtAgo(c.published_at)}</span>
                </li>
              ))}
            </ul>
          </Panel>
        </div>
      </DataState>
    </>
  );
}
