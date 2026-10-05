"use client";

import Link from "next/link";
import { useMemo } from "react";
import { ArrowUpRight, CircleAlert, OctagonAlert, TriangleAlert } from "lucide-react";
import { cells, claims, fmtAgo, fmtTime, overview, paginate, tenants, tz } from "@/mocks/data";
import type { Cell, Claim, Overview, Page } from "@/mocks/types";
import copy from "@/content/console.json";
import config from "@/config/live.json";
import { useList, useObject } from "@/lib/live/useData";
import { Badge, claimTone, DataState, MockTag, PageHeader, Panel } from "../ui";
import { LineChart } from "../charts";
import { DemoPanel } from "../DemoPanel";
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

/** Duplicate confirmations exist only in the prototype's mock data; the live API cannot see the board's bookings. */
function mockDuplicates(tenant: string) {
  const keys = new Set<string>();
  let duplicates = 0;
  for (const c of claims(tenant)) {
    if (c.state !== "CONFIRMED") continue;
    if (keys.has(c.target_job_key)) duplicates++;
    keys.add(c.target_job_key);
  }
  return duplicates;
}

const recentMock = (tenant: string): Page<Claim> => paginate(tenant, claims(tenant), null, config.recentClaims);

export function OverviewView() {
  const got = useObject<Overview>("/v1/overview", overview);
  const cellList = useList<Cell>("cells", cells);
  const recent = useObject<Page<Claim>>(`/v1/claims?limit=${config.recentClaims}`, recentMock);
  const { live, tenant, session } = got.source;
  const tenantName = live ? (session?.tenant.name ?? "") : (tenants.find((t) => t.id === tenant)?.name ?? tenant);

  const data = useMemo(() => {
    if (!got.data) return null;
    const c = got.data.claims;
    return {
      ...got.data,
      rate: c.finished ? Math.round((c.confirmed / c.finished) * 1000) / 10 : 0,
      window: fill(copy.common.minutes, { n: Math.round(c.window_s / 60) }),
    };
  }, [got.data]);

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      {live && session?.demo.tenant && <DemoPanel session={session} />}
      <DataState copy={p} rows={8} status={got.status} onRetry={got.retry}>
        {data && (
          <>
            <div className="grid grid-cols-2 gap-3 lg:grid-cols-4 lg:gap-4">
              <Tile label={p.tiles.workers} value={`${data.workers.healthy}/${data.workers.total}`} />
              <Tile label={fill(p.tiles.claims, { window: data.window })} value={String(data.claims.total)} />
              <Tile label={p.tiles.confirmRate} value={fill(copy.common.percent, { n: data.rate })} />
              {live ? (
                <Tile label={p.tiles.reconciling} value={String(data.claims.by_state.UNKNOWN ?? 0)} note={p.reconcilingNote} />
              ) : (
                <Tile label={p.tiles.duplicates} value={String(mockDuplicates(tenant))} note={p.duplicatesNote} />
              )}
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
                {data.alerts.length === 0 ? (
                  <p className="px-4 py-4 text-[13.5px] text-c-text-2 sm:px-5">{p.noAlerts}</p>
                ) : (
                  <ul className="divide-y divide-c-border">
                    {data.alerts.map((a) => {
                      const Icon = a.severity === "critical" ? OctagonAlert : a.severity === "warning" ? TriangleAlert : CircleAlert;
                      const tone = a.severity === "critical" ? "text-c-bad" : a.severity === "warning" ? "text-c-warn" : "text-c-info";
                      return (
                        <li key={a.id} className="flex gap-3 px-4 py-3 sm:px-5">
                          <Icon aria-hidden className={`mt-0.5 size-4 shrink-0 ${tone}`} />
                          <div className="min-w-0">
                            <p className="text-[13.5px] font-medium text-c-text">
                              <span className="sr-only">{a.severity}: </span>
                              {fill(p.alerts[a.kind], { n: a.count })}
                            </p>
                            <p className="mt-0.5 text-[12.5px] text-c-text-2">{p.alertDetails[a.kind]}</p>
                          </div>
                        </li>
                      );
                    })}
                  </ul>
                )}
              </Panel>
            </div>

            <div className="mt-4 grid gap-4 xl:grid-cols-[380px_minmax(0,1fr)]">
              <Panel title={p.cellsTitle}>
                {/* Only the viewer's own cell(s): a deployment can have many, and the rest are other tenants' business. */}
                <ul className="divide-y divide-c-border">
                  {cellList.rows.filter((c) => c.hosts_you).map((c) => (
                    <li key={c.id} className="px-4 py-3.5 sm:px-5">
                      <div className="flex items-center justify-between gap-3">
                        <p className="font-medium text-c-text">{c.name} <span className="font-normal text-c-text-3">· {c.region}</span></p>
                        {c.hosts_you && <Badge tone="info">{p.yourCell}</Badge>}
                      </div>
                      <div className="mt-2.5 h-1.5 overflow-hidden rounded-full bg-c-surface-3" aria-hidden>
                        <div className="h-full rounded-full bg-c-text-2" style={{ width: `${Math.min(100, (c.your_workers / c.capacity) * 100)}%` }} />
                      </div>
                      <p className="mt-2 text-[12.5px] text-c-text-2 tabular">
                        {fill(p.cellLine, { workers: c.your_workers, capacity: c.capacity, tenants: c.tenant_count })}
                      </p>
                    </li>
                  ))}
                </ul>
                {cellList.rows.some((c) => !c.hosts_you) && (
                  <p className="border-t border-c-border px-4 py-3 text-[12.5px] text-c-text-3 sm:px-5">
                    {fill(p.otherCells, { n: cellList.rows.filter((c) => !c.hosts_you).length })}
                  </p>
                )}
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
                  {(recent.data?.items ?? []).map((c) => (
                    <li key={c.id} className="flex flex-wrap items-center gap-x-4 gap-y-1 px-4 py-3 sm:px-5">
                      <span className="w-[86px] truncate font-mono text-[12.5px] text-c-text">{c.target_job_key}</span>
                      <Badge tone={claimTone[c.state]}>{copy.claimStates[c.state]}</Badge>
                      <span className="min-w-0 flex-1 truncate text-[13px] text-c-text-2">{c.lane}</span>
                      <span className="text-[12.5px] text-c-text-3 tabular">{fmtAgo(c.published_at ?? c.seen_at)}</span>
                    </li>
                  ))}
                </ul>
              </Panel>
            </div>
          </>
        )}
      </DataState>
    </>
  );
}
