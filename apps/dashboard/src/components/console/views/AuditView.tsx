"use client";

import { useMemo, useState } from "react";
import { Lock } from "lucide-react";
import { audit, fmtDateTime } from "@/mocks/data";
import type { AuditEntry } from "@/mocks/types";
import copy from "@/content/console.json";
import { useList } from "@/lib/live/useData";
import { DataState, LoadOlder, MockTag, PageHeader } from "../ui";
import { DataTable, type Column } from "../DataTable";
import { SearchInput, SelectFilter, Toolbar } from "../Toolbar";

const p = copy.pages.audit;

export function AuditView() {
  const list = useList<AuditEntry>("audit", audit);
  const { tenant } = list.source;
  const [query, setQuery] = useState("");
  const [action, setAction] = useState("all");
  const all = list.rows;
  const actions = useMemo(() => [...new Set(all.map((a) => a.action))].sort(), [all]);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return all.filter((a) => (action === "all" || a.action === action) && (!q || a.actor.toLowerCase().includes(q) || a.target.toLowerCase().includes(q)));
  }, [all, query, action]);

  const columns: Column<AuditEntry>[] = [
    { key: "at", header: p.columns.at, cell: (a) => <span className="whitespace-nowrap text-c-text-2 tabular">{fmtDateTime(a.at)}</span> },
    { key: "actor", header: p.columns.actor, cell: (a) => <span>{a.actor} <span className="text-[12px] text-c-text-3">· {a.role}</span></span> },
    { key: "action", header: p.columns.action, cell: (a) => <span className="font-mono text-[12.5px] text-c-accent-text">{a.action}</span> },
    { key: "target", header: p.columns.target, cell: (a) => <span className="font-mono text-[12.5px]">{a.target}</span> },
    { key: "detail", header: p.columns.detail, cell: (a) => <span className="text-c-text-2">{a.detail}</span> },
    { key: "ip", header: p.columns.ip, cell: (a) => <span className="font-mono text-[12px] text-c-text-3">{a.ip}</span> },
  ];

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p} status={list.status} onRetry={list.retry}>
        <Toolbar>
          <SearchInput id="audit-search" value={query} onChange={setQuery} placeholder={copy.common.searchPlaceholder} />
          <SelectFilter id="audit-action" label={p.columns.action} value={action} onChange={setAction} options={[{ value: "all", label: p.columns.action }, ...actions.map((a) => ({ value: a, label: a }))]} />
          <p className="flex items-center gap-1.5 text-[12.5px] text-c-text-3">
            <Lock aria-hidden className="size-3.5" /> {p.appendOnly}
          </p>
        </Toolbar>
        <DataTable label={p.title} tenant={tenant} rows={rows} columns={columns} rowKey={(a) => a.id} resetKey={`${tenant}|${action}|${query}`} />
        <LoadOlder hasMore={list.hasMore} loading={list.loadingMore} onMore={list.more} />
      </DataState>
    </>
  );
}
