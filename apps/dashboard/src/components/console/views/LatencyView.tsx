"use client";

import { useState } from "react";
import { ChartBar, Table2 } from "lucide-react";
import { fmtDuration, fmtMs, latency } from "@/mocks/data";
import type { Latency } from "@/mocks/types";
import { useObject } from "@/lib/live/useData";
import { fill } from "@/lib/fill";
import copy from "@/content/console.json";
import { DataState, MockTag, PageHeader, Panel } from "../ui";
import { GroupedBars } from "../charts";
import { RadioGroup } from "../RadioGroup";

const p = copy.pages.latency;
const KEYS = [
  { label: "p50", color: "var(--c-ord-1)" },
  { label: "p95", color: "var(--c-ord-2)" },
  { label: "p99", color: "var(--c-ord-3)" },
];

const mock = (tenant: string): Latency => ({ tenant_id: tenant, window_s: 3600, stages: latency(tenant) });

export function LatencyView() {
  const got = useObject<Latency>("/v1/latency", mock);
  const [view, setView] = useState<"chart" | "table">("chart");
  const stages = (got.data?.stages ?? []).map((s) => ({ ...s, label: p.stages[s.key] }));
  const note = got.source.live && got.data ? fill(p.liveNote, { window: fmtDuration(got.data.window_s) }) : p.note;

  const toggle = (
    <RadioGroup
      label={copy.common.viewLabel}
      value={view}
      onChange={setView}
      className="flex rounded-lg border border-c-border bg-c-surface p-0.5"
      options={[
        { value: "chart" as const, label: copy.common.viewChart, content: <><ChartBar aria-hidden className="size-3.5" /> {copy.common.viewChart}</> },
        { value: "table" as const, label: copy.common.viewTable, content: <><Table2 aria-hidden className="size-3.5" /> {copy.common.viewTable}</> },
      ]}
      optionClass={(on) => `inline-flex h-8 items-center gap-1.5 rounded-md px-2.5 text-[12.5px] ${on ? "bg-c-surface-3 text-c-text" : "text-c-text-3 hover:text-c-text"}`}
    />
  );

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p} rows={5} status={got.status} onRetry={got.retry}>
        <Panel title={p.chartTitle} aside={toggle}>
          <div className="p-4 sm:p-5">
            {view === "chart" ? (
              <GroupedBars
                title={p.chartTitle}
                groups={stages.map((s) => ({ id: s.key, label: s.label, values: [s.p50, s.p95, s.p99] }))}
                keys={KEYS}
                format={fmtMs}
              />
            ) : (
              <div className="overflow-x-auto" tabIndex={0} role="region" aria-label={p.chartTitle}>
                <table className="w-full min-w-[480px] text-left text-[13.5px]">
                  <caption className="sr-only">{p.chartTitle}</caption>
                  <thead>
                    <tr className="border-b border-c-border text-[12px] text-c-text-3">
                      <th scope="col" className="py-2 pr-4 font-medium">{p.columns.stage}</th>
                      <th scope="col" className="py-2 pr-4 text-right font-medium">{p.columns.p50}</th>
                      <th scope="col" className="py-2 pr-4 text-right font-medium">{p.columns.p95}</th>
                      <th scope="col" className="py-2 pr-4 text-right font-medium">{p.columns.p99}</th>
                      <th scope="col" className="py-2 text-right font-medium">{p.columns.samples}</th>
                    </tr>
                  </thead>
                  <tbody>
                    {stages.map((s) => (
                      <tr key={s.key} className="border-b border-c-border last:border-b-0">
                        <th scope="row" className="py-2.5 pr-4 font-normal text-c-text">
                          {s.label} <span className="ml-1 font-mono text-[11.5px] text-c-text-3">{s.key}</span>
                        </th>
                        <td className="py-2.5 pr-4 text-right tabular">{fmtMs(s.p50)}</td>
                        <td className="py-2.5 pr-4 text-right tabular">{fmtMs(s.p95)}</td>
                        <td className="py-2.5 pr-4 text-right tabular">{fmtMs(s.p99)}</td>
                        <td className="py-2.5 text-right tabular text-c-text-2">{s.samples}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            )}
            <p className="mt-4 text-[12.5px] text-c-text-3">{note}</p>
          </div>
        </Panel>
      </DataState>
    </>
  );
}
