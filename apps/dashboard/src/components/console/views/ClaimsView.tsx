"use client";

import { useCallback, useMemo, useRef, useState } from "react";
import { useDialog } from "@/lib/useDialog";
import { fill } from "@/lib/fill";
import { X } from "lucide-react";
import { claims, fmtAgo, fmtMs, fmtTime, fmtUsd } from "@/mocks/data";
import type { Claim, ClaimState } from "@/mocks/types";
import copy from "@/content/console.json";
import { useList, useLiveGet } from "@/lib/live/useData";
import { Badge, claimTone, DataState, LoadOlder, MockTag, PageHeader } from "../ui";
import { DataTable, type Column } from "../DataTable";
import { SearchInput, SelectFilter, Toolbar } from "../Toolbar";

const p = copy.pages.claims;
const STATES = Object.keys(copy.claimStates) as ClaimState[];

/** When the board posted the load, or (for boards that don't stamp it) when a watcher saw it. */
const startOf = (c: Claim) => c.published_at ?? c.seen_at;

function totalMs(c: Claim) {
  const end = c.confirmed_at ?? c.events[c.events.length - 1]?.at;
  return end ? Date.parse(end) - Date.parse(startOf(c)) : null;
}

function ClaimDrawer({ claim, onClose }: { claim: Claim; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null);
  const opener = useCallback(() => document.querySelector<HTMLElement>(`[data-claim-open="${claim.id}"]`), [claim.id]);
  useDialog(ref, onClose, undefined, opener);

  const start = Date.parse(startOf(claim));
  return (
    <div className="fixed inset-0 z-[var(--z-overlay)]">
      <button aria-label={copy.common.close} tabIndex={-1} className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby="claim-title" className="absolute inset-y-0 right-0 flex w-[min(460px,100vw)] flex-col border-l border-c-border bg-c-surface shadow-2xl">
        <div className="flex items-start justify-between gap-3 border-b border-c-border px-5 py-4">
          <div>
            <h2 id="claim-title" className="text-[17px] font-semibold text-c-text">{fill(p.detailTitle, { id: claim.id })}</h2>
            <p className="mt-1 text-[13px] text-c-text-2">{claim.target_job_key} · {claim.lane} · {fmtUsd(claim.rate_usd)}</p>
          </div>
          <button onClick={onClose} aria-label={copy.common.close} className="grid size-9 shrink-0 place-items-center rounded-lg text-c-text-2 hover:bg-c-surface-2">
            <X aria-hidden className="size-5" />
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-5 py-5">
          <dl className="grid grid-cols-2 gap-x-4 gap-y-3 text-[13px]">
            {[
              [p.columns.state, <Badge key="s" tone={claimTone[claim.state]}>{copy.claimStates[claim.state]}</Badge>],
              [p.columns.worker, <span key="w" className="font-mono">{claim.worker_id ?? copy.common.none}</span>],
              [p.columns.token, <span key="t" className="font-mono">{claim.fencing_token ?? copy.common.none}</span>],
              [p.tenantLabel, <span key="tn" className="font-mono">{claim.tenant_id}</span>],
            ].map(([k, v]) => (
              <div key={String(k)}>
                <dt className="text-c-text-3">{k}</dt>
                <dd className="mt-1 text-c-text">{v}</dd>
              </div>
            ))}
          </dl>
          <h3 className="mt-7 text-[13px] font-semibold text-c-text">{p.timeline}</h3>
          <ol className="mt-3 border-l border-c-border">
            {claim.published_at && (
              <li className="relative pb-5 pl-5">
                <span aria-hidden className="absolute -left-[5px] top-1 size-[9px] rounded-full bg-c-text-3" />
                <p className="text-[13px] text-c-text">{p.publishedEvent} <span className="text-c-text-3">· {p.publishedActor}</span></p>
                <p className="font-mono text-[12px] text-c-text-3">{fmtTime(claim.published_at)} · +{fmtMs(0)}</p>
              </li>
            )}
            {claim.events.map((e, i) => (
              <li key={i} className="relative pb-5 pl-5 last:pb-0">
                <span aria-hidden className={`absolute -left-[5px] top-1 size-[9px] rounded-full ${claimTone[e.state] === "ok" ? "bg-c-ok" : claimTone[e.state] === "bad" ? "bg-c-bad" : claimTone[e.state] === "warn" ? "bg-c-warn" : "bg-c-info"}`} />
                <div className="flex flex-wrap items-center gap-2">
                  <Badge tone={claimTone[e.state]}>{copy.claimStates[e.state]}</Badge>
                  <span className="text-[12.5px] text-c-text-2">{e.actor}</span>
                </div>
                {e.note && <p className="mt-1 text-[13px] text-c-text-2">{e.note}</p>}
                <p className="mt-0.5 font-mono text-[12px] text-c-text-3">{fmtTime(e.at)} · +{fmtMs(Date.parse(e.at) - start)}</p>
              </li>
            ))}
          </ol>
        </div>
      </div>
    </div>
  );
}

export function ClaimsView() {
  const [state, setState] = useState("all");
  const list = useList<Claim>("claims", claims, state === "all" ? "" : `state=${encodeURIComponent(state)}`);
  const { live, tenant } = list.source;
  const [query, setQuery] = useState("");
  const [openId, setOpenId] = useState<string | null>(null);
  const close = useCallback(() => setOpenId(null), []);

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return list.rows.filter(
      (c) => (state === "all" || c.state === state) && (!q || c.id.includes(q) || c.target_job_key.toLowerCase().includes(q) || c.lane.toLowerCase().includes(q)),
    );
  }, [list.rows, state, query]);
  // The list carries no timelines; live, the drawer fetches the full claim (it refreshes with the stream).
  const detail = useLiveGet<Claim>(live && openId ? `/v1/claims/${encodeURIComponent(openId)}` : null);
  const listed = openId ? list.rows.find((c) => c.id === openId) ?? null : null;
  const open = live ? (detail.data ?? listed) : listed;

  const columns: Column<Claim>[] = [
    {
      key: "id",
      header: p.columns.id,
      cell: (c) => (
        <button data-claim-open={c.id} onClick={() => setOpenId(c.id)} className="rounded font-mono text-[12.5px] text-c-accent-text underline-offset-2 hover:underline">
          {c.id}
        </button>
      ),
    },
    { key: "job", header: p.columns.job, cell: (c) => <span className="font-mono text-[12.5px]">{c.target_job_key}</span> },
    { key: "lane", header: p.columns.lane, cell: (c) => <span className="text-c-text-2">{c.lane}</span> },
    { key: "rate", header: p.columns.rate, align: "right", cell: (c) => fmtUsd(c.rate_usd) },
    { key: "state", header: p.columns.state, cell: (c) => <Badge tone={claimTone[c.state]}>{copy.claimStates[c.state]}</Badge> },
    { key: "worker", header: p.columns.worker, cell: (c) => <span className="font-mono text-[12.5px] text-c-text-2">{c.worker_id ?? "—"}</span> },
    { key: "token", header: p.columns.token, align: "right", cell: (c) => <span className="font-mono text-[12.5px] text-c-text-2">{c.fencing_token ?? "—"}</span> },
    { key: "published", header: p.columns.published, cell: (c) => <span className="text-c-text-2" title={fmtTime(startOf(c))}>{fmtAgo(startOf(c))}</span> },
    { key: "total", header: p.columns.total, align: "right", cell: (c) => { const t = totalMs(c); return t === null ? "—" : fmtMs(t); } },
  ];

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p} status={list.status} onRetry={list.retry}>
        <Toolbar>
          <SearchInput id="claim-search" value={query} onChange={setQuery} placeholder={copy.common.searchPlaceholder} />
          <SelectFilter
            id="claim-state"
            label={p.columns.state}
            value={state}
            onChange={setState}
            options={[{ value: "all", label: p.filterAll }, ...STATES.map((s) => ({ value: s, label: copy.claimStates[s] }))]}
          />
        </Toolbar>
        <DataTable label={p.title} tenant={tenant} rows={rows} columns={columns} rowKey={(c) => c.id} resetKey={`${tenant}|${state}|${query}`} />
        <LoadOlder hasMore={list.hasMore} loading={list.loadingMore} onMore={list.more} />
        {open && <ClaimDrawer claim={open} onClose={close} />}
      </DataState>
    </>
  );
}
