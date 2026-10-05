"use client";

import { useMemo, useState } from "react";
import { Lock, RefreshCw } from "lucide-react";
import { accounts, fmtAgo, fmtDuration } from "@/mocks/data";
import type { Account, SessionState } from "@/mocks/types";
import copy from "@/content/console.json";
import { usePrototype } from "../prototypeStore";
import { Badge, Button, DataState, MockTag, PageHeader, sessionTone } from "../ui";
import { DataTable, type Column } from "../DataTable";
import { Notice, SearchInput, Toolbar } from "../Toolbar";
import { fill } from "@/lib/fill";

const p = copy.pages.accounts;

export function AccountsView() {
  const { tenant } = usePrototype();
  const [query, setQuery] = useState("");
  const [refreshed, setRefreshed] = useState<Record<string, true>>({});
  const [notice, setNotice] = useState("");

  const rows = useMemo(() => {
    const q = query.trim().toLowerCase();
    return accounts(tenant)
      .map((a) => (refreshed[a.id] ? { ...a, session_state: "fresh" as SessionState, session_expires_in_s: a.session_ttl_s } : a))
      .filter((a) => !q || a.label.toLowerCase().includes(q) || a.id.includes(q));
  }, [tenant, query, refreshed]);

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
            <div className="h-full rounded-full bg-c-text-2" style={{ width: `${(a.session_expires_in_s / a.session_ttl_s) * 100}%` }} />
          </div>
          <span className="text-c-text-2 tabular">{a.session_expires_in_s ? fmtDuration(a.session_expires_in_s) : copy.common.none}</span>
        </div>
      ),
    },
    { key: "refreshed", header: p.columns.refreshed, cell: (a) => <span className="text-c-text-2">{fmtAgo(a.last_refresh_at)}</span> },
    { key: "otp", header: p.columns.otp, cell: (a) => <span className="capitalize text-c-text-2">{a.otp_channel}</span> },
    { key: "rate", header: p.columns.rate, align: "right", cell: (a) => fill(copy.common.perMinute, { n: a.rate_limit_per_min }) },
    {
      key: "actions",
      header: copy.common.actions,
      cell: (a) => (
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
      <DataState copy={p}>
        <Toolbar>
          <SearchInput id="account-search" value={query} onChange={setQuery} placeholder={copy.common.searchPlaceholder} />
          <p className="flex items-center gap-1.5 text-[12.5px] text-c-text-3">
            <Lock aria-hidden className="size-3.5" /> {p.credentialNote}
          </p>
          <Notice message={notice} />
        </Toolbar>
        <DataTable label={p.title} tenant={tenant} rows={rows} columns={columns} rowKey={(a) => a.id} resetKey={`${tenant}|${query}`} />
      </DataState>
    </>
  );
}
