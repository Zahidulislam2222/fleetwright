"use client";

import { useState } from "react";
import { apiGet, apiSend } from "@/lib/live/api";
import { useLive } from "@/lib/live/store";
import copy from "@/content/workflows.json";

type Job = { id: string; identity: string; workflow: string; account_id: string; state: string; action_hash: string; inputs?: Record<string, string> };
type JobPage = { jobs: Job[]; next_cursor: string | null };
type EvidencePage = { next_cursor: number | null };
const button = "rounded-lg border border-c-border bg-c-surface px-4 py-2 text-sm hover:bg-c-surface-2 disabled:opacity-50";

export function WorkflowsView() {
  const { session } = useLive();
  const [page, setPage] = useState<JobPage | null>(null);
  const [selected, setSelected] = useState<Job | null>(null);
  const [reviewed, setReviewed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [evidenceCursor, setEvidenceCursor] = useState<number | null>(0);
  const permitted = session?.authenticated && ["owner", "operator"].includes(session.role);

  async function request(operation: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try { await operation(); }
    catch { setMessage(copy.error); }
    finally { setBusy(false); }
  }

  async function listing(cursor?: string) {
    await request(async () => setPage(await apiGet<JobPage>(`/v1/workflows/jobs${cursor ? `?cursor=${encodeURIComponent(cursor)}` : ""}`)));
  }

  async function review(job: Job) {
    await request(async () => {
      setSelected(await apiGet<Job>(`/v1/workflows/jobs/${job.id}`));
      setReviewed(false);
      setEvidenceCursor(0);
    });
  }

  async function mutate(action: "approve" | "cancel") {
    if (!selected) return;
    await request(async () => {
      await apiSend("POST", `/v1/workflows/jobs/${selected.id}/${action}`, action === "approve" ? { action_hash: selected.action_hash } : undefined);
      setSelected(await apiGet<Job>(`/v1/workflows/jobs/${selected.id}`));
      setPage(await apiGet<JobPage>("/v1/workflows/jobs"));
      setReviewed(false);
      setMessage(action === "approve" ? copy.approved : copy.cancelled);
    });
  }

  async function download() {
    if (!selected || evidenceCursor === null) return;
    await request(async () => {
      const evidence = await apiGet<EvidencePage>(`/v1/workflows/jobs/${selected.id}/evidence?cursor=${evidenceCursor}`);
      const url = URL.createObjectURL(new Blob([JSON.stringify(evidence, null, 2)], { type: "application/json" }));
      const link = document.createElement("a");
      link.href = url;
      link.download = `workflow-${selected.id}-${evidenceCursor}.json`;
      link.click();
      URL.revokeObjectURL(url);
      setEvidenceCursor(evidence.next_cursor);
    });
  }

  return <section className="mx-auto max-w-5xl space-y-6 p-4 sm:p-8">
    <h1 className="text-2xl font-semibold">{copy.title}</h1>
    <p className="max-w-3xl text-c-text-2">{copy.intro}</p>
    {!permitted ? <p>{copy.access}</p> : <>
      <div className="flex flex-wrap gap-3">
        <button className={button} disabled={busy} onClick={() => void listing()}>{copy.refresh}</button>
        {page?.next_cursor && <button className={button} disabled={busy} onClick={() => void listing(page.next_cursor ?? undefined)}>{copy.older}</button>}
      </div>
      <p role="status" aria-live="polite">{busy ? copy.loading : message}</p>
      {page?.jobs.length === 0 && <p>{copy.empty}</p>}
      <ul className="space-y-3">{page?.jobs.map(job => <li key={job.id} className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-c-border p-4">
        <div className="min-w-0"><p>{job.workflow} · {job.state}</p><p className="break-all font-mono text-xs text-c-text-2">{job.identity}</p></div>
        <button className={button} disabled={busy} onClick={() => void review(job)}>{copy.review}</button>
      </li>)}</ul>
      {selected && <article aria-label={copy.review} className="space-y-4 rounded-xl border border-c-border p-5">
        <h2 className="text-lg font-semibold">{copy.review}</h2>
        <dl className="grid gap-3 break-all">
          {[[copy.workflow, selected.workflow], [copy.identity, selected.identity], [copy.account, selected.account_id], [copy.state, selected.state], [copy.hash, selected.action_hash]].map(([label, value]) => <div key={label}><dt className="text-sm text-c-text-2">{label}</dt><dd className="font-mono text-sm">{value}</dd></div>)}
          <div><dt className="text-sm text-c-text-2">{copy.inputs}</dt><dd><pre className="whitespace-pre-wrap break-all text-sm">{JSON.stringify(selected.inputs, null, 2)}</pre></dd></div>
        </dl>
        {selected.state === "UNKNOWN" && <p>{copy.unknown}</p>}
        {session?.role === "owner" && selected.state === "PENDING" && <label className="flex items-start gap-3"><input type="checkbox" checked={reviewed} onChange={event => setReviewed(event.target.checked)} />{copy.confirmation}</label>}
        <div className="flex flex-wrap gap-3">
          {session?.role === "owner" && selected.state === "PENDING" && <button className={button} disabled={busy || !reviewed} onClick={() => void mutate("approve")}>{copy.approve}</button>}
          <button className={button} disabled={busy || ["CONFIRMED", "FAILED", "CANCELLED"].includes(selected.state)} onClick={() => void mutate("cancel")}>{copy.cancel}</button>
          <button className={button} disabled={busy || evidenceCursor === null} onClick={() => void download()}>{evidenceCursor ? copy.nextEvidence : copy.evidence}</button>
          <button className={button} disabled={busy} onClick={() => setSelected(null)}>{copy.close}</button>
        </div>
      </article>}
    </>}
  </section>;
}
