"use client";

import { useMemo, useState } from "react";
import { Plus } from "lucide-react";
import { filters, fmtAgo, fmtUsd } from "@/mocks/data";
import type { Filter } from "@/mocks/types";
import copy from "@/content/console.json";
import { useList } from "@/lib/live/useData";
import { apiSend, ApiError } from "@/lib/live/api";
import { atLeast } from "@/lib/live/roles";
import { Button, DataState, MockTag, PageHeader } from "../ui";
import { DataTable, type Column } from "../DataTable";
import { Notice, SearchInput, Toolbar } from "../Toolbar";
import { fill } from "@/lib/fill";

const p = copy.pages.filters;

const L = copy.live;

function Toggle({ checked, onChange, label, disabledReason }: { checked: boolean; onChange: (v: boolean) => void; label: string; disabledReason?: string }) {
  return (
    <button
      role="switch"
      aria-checked={checked}
      aria-label={label}
      aria-disabled={disabledReason ? true : undefined}
      title={disabledReason}
      onClick={() => !disabledReason && onChange(!checked)}
      className="inline-flex items-center gap-2 rounded-full text-[12.5px] text-c-text-2"
    >
      <span className={`relative h-5 w-9 rounded-full transition-colors ${checked ? "bg-c-ok" : "bg-c-surface-3 ring-1 ring-c-border-strong"}`}>
        <span className={`absolute top-0.5 size-4 rounded-full bg-c-surface shadow transition-transform ${checked ? "translate-x-[18px]" : "translate-x-0.5"}`} />
      </span>
      {checked ? p.enabled : p.disabled}
    </button>
  );
}

function Input({ id, label, ...rest }: React.ComponentProps<"input"> & { id: string; label: string }) {
  return (
    <div>
      <label htmlFor={id} className="block text-[12.5px] text-c-text-2">{label}</label>
      <input id={id} {...rest} className="mt-1 h-9 w-full rounded-lg border border-c-input-border bg-c-surface px-3 text-[14px] text-c-text" />
    </div>
  );
}

/** Creates a filter through the API. Validation is the server's; its message is shown as is. */
function NewFilterForm({ onDone }: { onDone: (message: string) => void }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <form
      aria-labelledby="new-filter-title"
      className="mb-4 grid gap-3 rounded-2xl border border-c-border bg-c-surface p-4 sm:grid-cols-2 lg:grid-cols-3"
      onSubmit={(e) => {
        e.preventDefault();
        const f = new FormData(e.currentTarget);
        const text = (k: string) => String(f.get(k) ?? "").trim();
        const body = {
          name: text("name"),
          origin: text("origin") || L.filter.any,
          destination: text("destination") || L.filter.any,
          min_rate_usd: Number(text("min_rate_usd") || 0),
          equipment: text("equipment").split(",").map((x) => x.trim()).filter(Boolean),
          max_weight_lb: Number(text("max_weight_lb") || 0) || undefined,
        };
        setBusy(true);
        setError("");
        apiSend<Filter>("POST", "/v1/filters", body)
          .then((created) => onDone(fill(L.filter.created, { name: created.name })))
          .catch((err: unknown) => setError(fill(L.failed, { detail: err instanceof ApiError ? err.message : String(err) })))
          .finally(() => setBusy(false));
      }}
    >
      <h2 id="new-filter-title" className="text-[14.5px] font-semibold text-c-text sm:col-span-2 lg:col-span-3">{L.filter.title}</h2>
      <Input id="nf-name" name="name" label={L.filter.name} required maxLength={80} autoFocus />
      <Input id="nf-origin" name="origin" label={L.filter.origin} placeholder={L.filter.any} maxLength={80} />
      <Input id="nf-destination" name="destination" label={L.filter.destination} placeholder={L.filter.any} maxLength={80} />
      <Input id="nf-rate" name="min_rate_usd" label={L.filter.minRate} type="number" min={0} step={1} inputMode="numeric" />
      <Input id="nf-equipment" name="equipment" label={L.filter.equipment} maxLength={200} />
      <Input id="nf-weight" name="max_weight_lb" label={L.filter.maxWeight} type="number" min={1} step={1} inputMode="numeric" />
      <div className="flex flex-wrap items-center gap-2 sm:col-span-2 lg:col-span-3">
        <Button type="submit" variant="primary" disabled={busy}>{L.filter.create}</Button>
        <Button type="button" variant="ghost" onClick={() => onDone("")}>{L.filter.cancel}</Button>
        {error && <p role="alert" className="text-[13px] text-c-bad">{error}</p>}
      </div>
    </form>
  );
}

export function FiltersView() {
  const list = useList<Filter>("filters", filters);
  const { live, tenant, session } = list.source;
  const canEdit = atLeast(session, "operator");
  const needs = live && !canEdit ? fill(L.needsRole, { role: L.roles.operator }) : undefined;
  const [creating, setCreating] = useState(false);
  const [query, setQuery] = useState("");
  // Optimistic toggles, valid only for the version they were made on: the server bumps `version` on
  // every edit, so fresh data replaces the override without a flicker (and the prototype keeps it).
  const [enabled, setEnabled] = useState<Record<string, { on: boolean; version: number }>>({});
  const shown = (f: Filter) => (enabled[f.id]?.version === f.version ? enabled[f.id].on : f.enabled);
  const [notice, setNotice] = useState("");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return list.rows.filter((f) => !q || f.name.toLowerCase().includes(q) || f.origin.toLowerCase().includes(q));
  }, [list.rows, query]);

  const columns: Column<Filter>[] = [
    {
      key: "enabled",
      header: p.enabled,
      cell: (f) => (
        <Toggle
          checked={shown(f)}
          label={`${f.name} ${p.enabled.toLowerCase()}`}
          disabledReason={needs}
          onChange={(v) => {
            setEnabled((e) => ({ ...e, [f.id]: { on: v, version: f.version } }));
            if (!live) {
              setNotice(fill(copy.common.prototypeAction, { action: v ? p.enabled : p.disabled, target: f.name }));
              return;
            }
            apiSend<Filter>("PATCH", `/v1/filters/${encodeURIComponent(f.id)}`, { enabled: v })
              .then(() => setNotice(fill(L.filter.toggled, { name: f.name, state: (v ? p.enabled : p.disabled).toLowerCase() })))
              .catch((err: unknown) => {
                setEnabled((e) => {
                  const next = { ...e };
                  delete next[f.id];
                  return next;
                });
                setNotice(fill(L.failed, { detail: err instanceof ApiError ? err.message : String(err) }));
              })
              .finally(list.retry);
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
            <Button
              variant="primary"
              aria-disabled={needs ? true : undefined}
              title={needs}
              onClick={() => {
                if (needs) return;
                if (live) setCreating(true);
                else setNotice(fill(copy.common.prototypeAction, { action: p.new, target: tenant }));
              }}
            >
              <Plus aria-hidden className="size-4" /> {p.new}
            </Button>
          </>
        }
      />
      {creating && (
        <NewFilterForm
          onDone={(message) => {
            setCreating(false);
            setNotice(message);
            if (message) list.retry();
          }}
        />
      )}
      <DataState copy={p} status={list.status} onRetry={list.retry}>
        <Toolbar>
          <SearchInput id="filter-search" value={query} onChange={setQuery} placeholder={copy.common.searchPlaceholder} />
          <Notice message={notice} />
        </Toolbar>
        <DataTable label={p.title} tenant={tenant} rows={rows} columns={columns} rowKey={(f) => f.id} resetKey={`${tenant}|${query}`} />
      </DataState>
    </>
  );
}
