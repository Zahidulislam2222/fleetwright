"use client";

import { useState } from "react";
import { ShieldCheck, ShieldX } from "lucide-react";
import { cells, fmtAgo, tenants, users } from "@/mocks/data";
import type { Cell, User } from "@/mocks/types";
import { useList } from "@/lib/live/useData";
import copy from "@/content/console.json";
import { Badge, Button, DataState, MockTag, PageHeader, Panel } from "../ui";
import { Notice } from "../Toolbar";
import { fill } from "@/lib/fill";

const p = copy.pages.settings;

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid gap-1.5 px-4 py-3.5 sm:grid-cols-[220px_minmax(0,1fr)] sm:items-center sm:gap-4 sm:px-5">
      <dt className="text-[13.5px] text-c-text-2">{label}</dt>
      <dd className="text-[14px] text-c-text">{children}</dd>
    </div>
  );
}

export function SettingsView() {
  const people = useList<User>("users", users);
  const cellList = useList<Cell>("cells", cells);
  const { live, tenant, session } = people.source;
  const mockTenant = tenants.find((x) => x.id === tenant) ?? tenants[0];
  const t = live && session ? { id: session.tenant.id, name: session.tenant.name } : { id: mockTenant.id, name: mockTenant.name };
  const cell = cellList.rows.find((c) => c.hosts_you);
  const [name, setName] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p} rows={6} status={people.status} onRetry={people.retry}>
        <div className="grid gap-4">
          <Panel title={p.sections.tenant}>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setNotice(live ? p.liveNote : p.prototypeNote);
              }}
            >
              <dl className="divide-y divide-c-border">
                <Row label={p.fields.tenantName}>
                  <label htmlFor="tenant-name" className="sr-only">{p.fields.tenantName}</label>
                  <input
                    id="tenant-name"
                    value={name[tenant] ?? t.name}
                    readOnly={live}
                    onChange={(e) => setName((n) => ({ ...n, [tenant]: e.target.value }))}
                    maxLength={80}
                    className="h-9 w-full max-w-[360px] rounded-lg border border-c-input-border bg-c-surface px-3 text-[14px] text-c-text"
                  />
                </Row>
                <Row label={p.fields.tenantId}><span className="font-mono text-[13px]">{t.id}</span></Row>
                <Row label={p.fields.cell}>{cell ? `${cell.name} · ${cell.region}` : copy.common.none}</Row>
              </dl>
              <div className="flex flex-wrap items-center gap-3 border-t border-c-border px-4 py-3 sm:px-5">
                {!live && <Button type="submit" variant="primary">{p.save}</Button>}
                {live && <p className="text-[12.5px] text-c-text-3">{p.liveNote}</p>}
                <Notice message={notice} />
              </div>
            </form>
          </Panel>

          <Panel title={p.sections.people}>
            <ul className="divide-y divide-c-border">
              {people.rows.map((u) => (
                <li key={u.id} className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-3 sm:px-5">
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-medium text-c-text">{u.name}</p>
                    <p className="text-[12.5px] text-c-text-3">{u.email}{u.last_seen_at && <> · {fill(copy.common.seen, { t: fmtAgo(u.last_seen_at) })}</>}</p>
                  </div>
                  <Badge tone="neutral">{p.roles[u.role]}</Badge>
                  {u.mfa ? <Badge tone="ok" icon={ShieldCheck}>{p.mfaOn}</Badge> : <Badge tone="warn" icon={ShieldX}>{p.mfaOff}</Badge>}
                </li>
              ))}
            </ul>
          </Panel>

          <div className="grid gap-4 lg:grid-cols-2">
            <Panel title={p.sections.security}>
              <dl className="divide-y divide-c-border">
                <Row label={p.fields.mfa}><Badge tone="ok" icon={ShieldCheck}>{p.mfaOn}</Badge></Row>
                {/* Timeout and retention values are prototype copy, not read from the server: hidden when live. */}
                {!live && <Row label={p.fields.sessionTimeout}>{p.values.sessionTimeout}</Row>}
              </dl>
            </Panel>
            {!live && (
            <Panel title={p.sections.retention}>
              <dl className="divide-y divide-c-border">
                <Row label={p.fields.retentionAudit}>{p.values.retentionAudit}</Row>
                <Row label={p.fields.retentionClaims}>{p.values.retentionClaims}</Row>
                <Row label={p.fields.retentionCrawl}>{p.values.retentionCrawl}</Row>
              </dl>
            </Panel>
            )}
          </div>
        </div>
      </DataState>
    </>
  );
}
