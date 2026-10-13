"use client";

import { useState } from "react";
import copy from "@/content/crawls.json";
import { apiSend } from "@/lib/live/api";
import { atLeast } from "@/lib/live/roles";
import { useLive } from "@/lib/live/store";
import { useLiveGet } from "@/lib/live/useData";
import { Button, PageHeader, Panel } from "../ui";

type Crawl = {
  id: string; definition: string; state: string; pages: number; items: number; errors: number;
  added: number; changed: number; removed: number; alerts: string[];
  export_available: boolean;
};
type CrawlPage = { items: Crawl[]; next_cursor: string | null };
type Contracts = Record<string, { name: string; personal_data: boolean; respect_robots: boolean }>;

export function LiveCrawlView() {
  const { session } = useLive();
  const [cursor, setCursor] = useState<string | null>(null);
  const [definition, setDefinition] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const contracts = useLiveGet<Contracts>("/v1/crawls/contracts");
  const page = useLiveGet<CrawlPage>(`/v1/crawls/jobs${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`);
  const permitted = atLeast(session, "operator");
  const chosen = definition || Object.keys(contracts.data ?? {})[0] || "";

  async function mutate(path: string, body?: { definition: string }) {
    setBusy(true);
    setMessage("");
    try {
      await apiSend("POST", path, body);
      setMessage(body ? copy.queued : copy.cancelled);
      page.reload();
    } catch { setMessage(copy.error); }
    finally { setBusy(false); }
  }

  return <>
    <PageHeader title={copy.title} description={copy.description} />
    <Panel>
      <div className="space-y-4 p-4 sm:p-5">
        <p className="max-w-3xl text-sm text-c-text-2">{copy.policy}</p>
        <div className="flex flex-wrap items-end gap-3">
          {permitted && <><label className="grid gap-1 text-sm">{copy.definition}
            <select aria-label={copy.definition} value={chosen} onChange={event => setDefinition(event.target.value)} className="rounded-lg border border-c-border bg-c-surface px-3 py-2">
              {Object.entries(contracts.data ?? {}).map(([key, contract]) => <option key={key} value={key}>{contract.name}</option>)}
            </select>
          </label>
          <Button variant="primary" disabled={busy || !chosen} onClick={() => void mutate("/v1/crawls/jobs", { definition: chosen })}>{copy.start}</Button></>}
          <Button disabled={busy} onClick={() => { setCursor(null); page.reload(); }}>{copy.refresh}</Button>
          {page.data?.next_cursor && <Button disabled={busy} onClick={() => setCursor(page.data?.next_cursor ?? null)}>{copy.older}</Button>}
        </div>
        {!permitted && <p className="text-sm text-c-text-2">{copy.access}</p>}
        <p role="status" aria-live="polite" className="text-sm">{page.status === "loading" ? copy.loading : page.status === "error" || page.status === "denied" ? copy.error : message}</p>
        {page.data?.items.length === 0 && <p>{copy.empty}</p>}
      </div>
      <ul className="divide-y divide-c-border">{page.data?.items.map(job => <li key={job.id} className="space-y-3 p-4 sm:p-5">
        <div className="flex flex-wrap items-center justify-between gap-3"><div>
          <h2 className="font-semibold">{contracts.data?.[job.definition]?.name ?? job.definition} · {job.state}</h2>
          <p className="break-all font-mono text-xs text-c-text-3">{job.id}</p>
        </div>
        {permitted && <div className="flex gap-3">
          {["QUEUED", "RUNNING"].includes(job.state) && <Button disabled={busy} onClick={() => void mutate(`/v1/crawls/jobs/${job.id}/cancel`)}>{copy.cancel}</Button>}
          {job.export_available && <a className="rounded-lg border border-c-border px-3 py-2 text-sm" href={`/v1/crawls/jobs/${job.id}/export`}>{copy.download}</a>}
        </div>}</div>
        <dl className="flex flex-wrap gap-x-6 gap-y-2 text-sm">
          {[[copy.pages, job.pages], [copy.items, job.items], [copy.errors, job.errors], [copy.changes, `${job.added} / ${job.changed} / ${job.removed}`]].map(([label, value]) => <div key={label}><dt className="text-c-text-3">{label}</dt><dd className="font-mono">{value}</dd></div>)}
        </dl>
        {job.alerts.map(alert => <p key={alert} role="note" className="rounded-lg bg-c-warn-bg px-3 py-2 text-sm">{copy.alerts[alert as keyof typeof copy.alerts] ?? alert}</p>)}
      </li>)}</ul>
    </Panel>
  </>;
}
