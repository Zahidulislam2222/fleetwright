"use client";

import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { filters, fmtAgo, fmtUsd } from "@/mocks/data";
import type { Filter } from "@/mocks/types";
import copy from "@/content/console.json";
import { usePrototype } from "../prototypeStore";
import { Button, DataState, MockTag, PageHeader } from "../ui";
import { DataTable, type Column } from "../DataTable";
import { Notice, SearchInput, Toolbar } from "../Toolbar";
import { fill } from "@/lib/fill";

const p = copy.pages.filters;

function Toggle({ checked, onChange, label }: { checked: boolean; onChange: (v: boolean) => void; label: string }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      onClick={() => onChange(!checked)}
      className="inline-flex items-center gap-2 rounded-full text-[12.5px] text-c-text-2"
    >
      <span className={`relative h-5 w-9 rounded-full transition-colors ${checked ? "bg-c-ok" : "bg-c-surface-3 ring-1 ring-c-border-strong"}`}>
        <span className={`absolute top-0.5 size-4 rounded-full bg-c-surface shadow transition-transform ${checked ? "translate-x-[18px]" : "translate-x-0.5"}`} />
      </span>
      {checked ? p.enabled : p.disabled}
    </button>
  );
}

export function FiltersView() {
  const { tenant } = usePrototype();
  const [query, setQuery] = useState("");
  const [enabled, setEnabled] = useState<Record<string, boolean>>({});
  const [notice, setNotice] = useState("");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return filters(tenant).filter((f) => !q || f.name.toLowerCase().includes(q) || f.origin.toLowerCase().includes(q));
  }, [tenant, query]);

  const columns: Column<Filter>[] = [
    {
      key: "enabled",
      header: p.enabled,
      cell: (f) => (
        <Toggle
          checked={enabled[f.id] ?? f.enabled}
          label={`${f.name} ${p.enabled.toLowerCase()}`}
          onChange={(v) => {
            setEnabled((e) => ({ ...e, [f.id]: v }));
            setNotice(fill(copy.common.prototypeAction, { action: v ? p.enabled : p.disabled, target: f.name }));
          }}
        />
      ),
    },
    { key: "name", header: p.columns.name, cell: (f) => <span className="font-medium">{f.name}</span> },
    { key: "lane", header: p.columns.lane, cell: (f) => <span className="text-c-text-2">{f.origin} → {f.destination}</span> },
    { key: "rate", header: p.columns.rate, align: "right", cell: (f) => fmtUsd(f.min_rate_usd) },
    { key: "equipment", header: p.columns.equipment, cell: (f) => <span className="text-c-text-2">{f.equipment.join(", ")}</span> },
    { key: "weight", header: p.columns.weight, align: "right", cell: (f) => fill(copy.common.weightLb, { n: f.max_weight_lb.toLocaleString("en-US") }) },
    { key: "group", header: p.columns.group, cell: (f) => <span className="text-c-text-2">{f.account_group}</span> },
    { key: "matched", header: p.columns.matched, align: "right", cell: (f) => f.matched_24h },
    { key: "version", header: p.columns.version, cell: (f) => <span className="font-mono text-[12px] text-c-text-3" title={fill(copy.common.updated, { t: fmtAgo(f.updated_at) })}>{fill(copy.common.version, { n: f.version })}</span> },
  ];

  return (
    <>
      <PageHeader
        title={p.title}
        description={p.description}
        actions={
          <>
            <MockTag />
            <Button variant="primary" onClick={() => setNotice(fill(copy.common.prototypeAction, { action: p.new, target: tenant }))}>
              <Plus aria-hidden className="size-4" /> {p.new}
            </Button>
          </>
        }
      />
      <DataState copy={p}>
        <Toolbar>
          <SearchInput id="filter-search" value={query} onChange={setQuery} placeholder={copy.common.searchPlaceholder} />
          <Notice message={notice} />
        </Toolbar>
        <DataTable label={p.title} tenant={tenant} rows={rows} columns={columns} rowKey={(f) => f.id} resetKey={`${tenant}|${query}`} />
      </DataState>
    </>
  );
}
