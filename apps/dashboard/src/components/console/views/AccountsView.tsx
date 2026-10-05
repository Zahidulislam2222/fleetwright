"use client";

import { useMemo, useState } from "react";
import { KeyRound, Lock, RefreshCw } from "lucide-react";
import { accounts, fmtAgo, fmtDuration } from "@/mocks/data";
import type { Account, SessionState } from "@/mocks/types";
import copy from "@/content/console.json";
import { useList } from "@/lib/live/useData";
import { apiSend, ApiError } from "@/lib/live/api";
import { atLeast } from "@/lib/live/roles";
import { Badge, Button, DataState, MockTag, PageHeader, sessionTone } from "../ui";
import { DataTable, type Column } from "../DataTable";
import { Notice, SearchInput, Toolbar } from "../Toolbar";
import { fill } from "@/lib/fill";

const p = copy.pages.accounts;

const L = copy.live;

/** Sends the one-time code an operator received to the worker waiting for it. */
function OtpForm({ account, onDone }: { account: Account; onDone: (message: string) => void }) {
  const [code, setCode] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  return (
    <form
      className="flex flex-wrap items-end gap-2 rounded-xl border border-c-border bg-c-surface-2 p-3"
      onSubmit={(e) => {
        e.preventDefault();
        setBusy(true);
        setError("");
        apiSend("POST", `/v1/accounts/${encodeURIComponent(account.id)}/otp`, { code: code.trim() })
          .then(() => onDone(L.otp.sent))
          .catch((err: unknown) => setError(fill(L.failed, { detail: err instanceof ApiError ? err.message : String(err) })))
          .finally(() => setBusy(false));
      }}
    >
      <div>
        <label htmlFor="otp-code" className="block text-[12.5px] text-c-text-2">{fill(L.otp.label, { account: account.label })}</label>
        <input
          id="otp-code"
          autoFocus
          value={code}
          onChange={(e) => setCode(e.target.value)}
          inputMode="numeric"
          autoComplete="one-time-code"
          maxLength={12}
          pattern="[0-9A-Za-z]{4,12}"
          required
          className="mt-1 h-9 w-40 rounded-lg border border-c-input-border bg-c-surface px-3 font-mono text-[14px] tracking-[0.2em] text-c-text"
        />
      </div>
      <Button type="submit" variant="primary" disabled={busy}>{L.otp.submit}</Button>
      <Button type="button" variant="ghost" onClick={() => onDone("")}>{L.filter.cancel}</Button>
      <p className="basis-full text-[12px] text-c-text-3">{L.otp.note}</p>
      {error && <p role="alert" className="basis-full text-[13px] text-c-bad">{error}</p>}
    </form>
  );
}

export function AccountsView() {
  const list = useList<Account>("accounts", accounts);
  const { live, tenant, session } = list.source;
  const canOperate = atLeast(session, "operator");
  const [otpFor, setOtpFor] = useState<Account | null>(null);
  const [query, setQuery] = useState("");
  const [refreshed, setRefreshed] = useState<Record<string, true>>({});
  const [notice, setNotice] = useState("");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return list.rows
      .map((a) => (refreshed[a.id] ? { ...a, session_state: "fresh" as SessionState, session_expires_in_s: a.session_ttl_s } : a))
      .filter((a) => !q || a.label.toLowerCase().includes(q) || a.id.includes(q));
  }, [list.rows, query, refreshed]);

  const columns: Column<Account>[] = [
    {
      key: "label",
      header: p.columns.label,
      cell: (a) => (
        <div>
          <p className="font-medium">{a.label}</p>
          <p className="font-mono text-[11.5px] text-c-text-3">{a.id} · {a.target}</p>
        </div>
      ),
    },
    { key: "session", header: p.columns.session, cell: (a) => <Badge tone={sessionTone[a.session_state]}>{p.sessionStates[a.session_state]}</Badge> },
    {
      key: "expires",
      header: p.columns.expires,
      cell: (a) => (
        <div className="flex min-w-[140px] items-center gap-2">
          <div className="h-1.5 w-20 overflow-hidden rounded-full bg-c-surface-3" aria-hidden>
            <div className="h-full rounded-full bg-c-text-2" style={{ width: `${a.session_ttl_s ? Math.min(100, (a.session_expires_in_s / a.session_ttl_s) * 100) : 0}%` }} />
          </div>
          <span className="text-c-text-2 tabular">{a.session_expires_in_s ? fmtDuration(a.session_expires_in_s) : copy.common.none}</span>
        </div>
      ),
    },
    { key: "refreshed", header: p.columns.refreshed, cell: (a) => <span className="text-c-text-2">{a.last_refresh_at ? fmtAgo(a.last_refresh_at) : copy.common.none}</span> },
    { key: "otp", header: p.columns.otp, cell: (a) => <span className="capitalize text-c-text-2">{a.otp_channel}</span> },
    { key: "rate", header: p.columns.rate, align: "right", cell: (a) => fill(copy.common.perMinute, { n: a.rate_limit_per_min }) },
    {
      key: "actions",
      header: copy.common.actions,
      cell: (a) =>
        live ? (
          a.session_state === "otp_required" && canOperate ? (
            <Button variant="ghost" className="h-8 px-2.5" aria-label={`${L.otp.enter}: ${a.label}`} onClick={() => setOtpFor(a)}>
              <KeyRound aria-hidden className="size-3.5" /> {L.otp.enter}
            </Button>
          ) : (
            <span className="text-c-text-3">{copy.common.none}</span>
          )
        ) : (
        <Button
          variant="ghost"
          className="h-8 px-2.5"
          aria-disabled={a.session_state === "fresh"}
          aria-label={`${p.refresh}: ${a.label}`}
          onClick={() => {
            if (a.session_state === "fresh") return;
            setRefreshed((r) => ({ ...r, [a.id]: true }));
            setNotice(fill(copy.common.prototypeAction, { action: p.refresh, target: a.label }));
          }}
        >
          <RefreshCw aria-hidden className="size-3.5" /> {p.refresh}
        </Button>
        ),
    },
  ];

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p} status={list.status} onRetry={list.retry}>
        <Toolbar>
          <SearchInput id="account-search" value={query} onChange={setQuery} placeholder={copy.common.searchPlaceholder} />
          <p className="flex items-center gap-1.5 text-[12.5px] text-c-text-3">
            <Lock aria-hidden className="size-3.5" /> {p.credentialNote}
          </p>
          <Notice message={notice} />
        </Toolbar>
        {otpFor && (
          <div className="mb-4">
            <OtpForm
              account={otpFor}
              onDone={(message) => {
                setOtpFor(null);
                setNotice(message);
              }}
            />
          </div>
        )}
        <DataTable label={p.title} tenant={tenant} rows={rows} columns={columns} rowKey={(a) => a.id} resetKey={`${tenant}|${query}`} />
      </DataState>
    </>
  );
}
