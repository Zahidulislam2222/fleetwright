"use client";

import { useMemo, useState } from "react";
import { fmtAgo, fmtDuration, workers } from "@/mocks/data";
import type { Worker, WorkerStatus } from "@/mocks/types";
import copy from "@/content/console.json";
import { useList } from "@/lib/live/useData";
import { Badge, Button, DataState, MockTag, PageHeader, workerTone } from "../ui";
import { DataTable, type Column } from "../DataTable";
import { Notice, SearchInput, SelectFilter, Toolbar } from "../Toolbar";
import { fill } from "@/lib/fill";

const p = copy.pages.workers;

export function WorkersView() {
  const list = useList<Worker>("workers", workers);
  const { live, tenant } = list.source;
  const [status, setStatus] = useState("all");
  const [query, setQuery] = useState("");
  const [overrides, setOverrides] = useState<Record<string, WorkerStatus>>({});
  const [notice, setNotice] = useState("");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return list.rows
      .map((w) => (overrides[w.id] ? { ...w, status: overrides[w.id] } : w))
      .filter((w) => (status === "all" || w.status === status) && (!q || w.id.includes(q) || (w.account_id ?? "").includes(q)));
  }, [list.rows, status, query, overrides]);

  const act = (w: Worker, action: string) => {
    // aria-disabled (not disabled) keeps the focused button in place after the action.
    if (action === p.actions.drain && w.status !== "healthy") return;
    if (action === p.actions.drain) setOverrides((o) => ({ ...o, [w.id]: "draining" }));
    setNotice(fill(copy.common.prototypeAction, { action, target: w.id }));
  };

  const columns: Column<Worker>[] = [
    { key: "id", header: p.columns.id, cell: (w) => <span className="font-mono text-[12.5px]">{w.id}</span> },
    { key: "mode", header: p.columns.mode, cell: (w) => <span className="capitalize text-c-text-2">{w.mode}</span> },
    { key: "status", header: p.columns.status, cell: (w) => <Badge tone={workerTone[w.status]}>{copy.status[w.status]}</Badge> },
    { key: "account", header: p.columns.account, cell: (w) => <span className="font-mono text-[12.5px] text-c-text-2">{w.account_id ?? copy.common.none}</span> },
    { key: "contexts", header: p.columns.contexts, align: "right", cell: (w) => w.contexts },
    { key: "cpu", header: p.columns.cpu, align: "right", cell: (w) => fill(copy.common.percent, { n: w.cpu_pct }) },
    { key: "memory", header: p.columns.memory, align: "right", cell: (w) => (w.memory_mb ? fill(copy.common.megabytes, { n: w.memory_mb }) : copy.common.none) },
    {
      key: "heartbeat",
      header: p.columns.heartbeat,
      align: "right",
      cell: (w) => <span className={w.heartbeat_age_s > 30 ? "text-c-bad" : ""}>{fill(copy.common.ago, { t: fmtDuration(w.heartbeat_age_s) })}</span>,
    },
    { key: "version", header: p.columns.version, cell: (w) => <span className="font-mono text-[12px] text-c-text-3" title={fill(copy.common.started, { t: fmtAgo(w.started_at) })}>{w.version}</span> },
    // Drain and restart exist only in the prototype; the live API has no worker controls yet.
    ...(live ? [] : [{
      key: "actions",
      header: copy.common.actions,
      cell: (w) => (
        <div className="flex gap-1">
          <Button variant="ghost" className="h-8 px-2.5" aria-disabled={w.status !== "healthy"} onClick={() => act(w, p.actions.drain)} aria-label={`${p.actions.drain} ${w.id}`}>
            {p.actions.drain}
          </Button>
          <Button variant="ghost" className="h-8 px-2.5" onClick={() => act(w, p.actions.restart)} aria-label={`${p.actions.restart} ${w.id}`}>
            {p.actions.restart}
          </Button>
        </div>
      ),
    } satisfies Column<Worker>]),
  ];

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p} status={list.status} onRetry={list.retry}>
        <Toolbar>
          <SearchInput id="worker-search" value={query} onChange={setQuery} placeholder={copy.common.searchPlaceholder} />
          <SelectFilter
            id="worker-status"
            label={p.columns.status}
            value={status}
            onChange={setStatus}
            options={[{ value: "all", label: p.filterAll }, ...(["healthy", "draining", "stale", "dead"] as const).map((s) => ({ value: s, label: copy.status[s] }))]}
          />
          {live && <p className="text-[12.5px] text-c-text-3">{copy.live.workerActionsNote}</p>}
          <Notice message={notice} />
        </Toolbar>
        <DataTable label={p.title} tenant={tenant} rows={rows} columns={columns} rowKey={(w) => w.id} resetKey={`${tenant}|${status}|${query}`} />
      </DataState>
    </>
  );
}
