"use client";

import { useState } from "react";
import { ShieldCheck, ShieldX } from "lucide-react";
import { cells, fmtAgo, tenants, users } from "@/mocks/data";
import copy from "@/content/console.json";
import { usePrototype } from "../prototypeStore";
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
  const { tenant } = usePrototype();
  const t = tenants.find((x) => x.id === tenant) ?? tenants[0];
  const cell = cells().find((c) => c.id === t.cell);
  const [name, setName] = useState<Record<string, string>>({});
  const [notice, setNotice] = useState("");

  return (
    <>
      <PageHeader title={p.title} description={p.description} actions={<MockTag />} />
      <DataState copy={p} rows={6}>
        <div className="grid gap-4">
          <Panel title={p.sections.tenant}>
            <form
              onSubmit={(e) => {
                e.preventDefault();
                setNotice(p.prototypeNote);
              }}
            >
              <dl className="divide-y divide-c-border">
                <Row label={p.fields.tenantName}>
                  <label htmlFor="tenant-name" className="sr-only">{p.fields.tenantName}</label>
                  <input
                    id="tenant-name"
                    value={name[tenant] ?? t.name}
                    onChange={(e) => setName((n) => ({ ...n, [tenant]: e.target.value }))}
                    maxLength={80}
                    className="h-9 w-full max-w-[360px] rounded-lg border border-c-input-border bg-c-surface px-3 text-[14px] text-c-text"
                  />
                </Row>
                <Row label={p.fields.tenantId}><span className="font-mono text-[13px]">{t.id}</span></Row>
                <Row label={p.fields.cell}>{cell ? `${cell.name} · ${cell.region}` : t.cell}</Row>
              </dl>
              <div className="flex flex-wrap items-center gap-3 border-t border-c-border px-4 py-3 sm:px-5">
                <Button type="submit" variant="primary">{p.save}</Button>
                <Notice message={notice} />
              </div>
            </form>
          </Panel>

          <Panel title={p.sections.people}>
            <ul className="divide-y divide-c-border">
              {users(tenant).map((u) => (
                <li key={u.id} className="flex flex-wrap items-center gap-x-4 gap-y-1.5 px-4 py-3 sm:px-5">
                  <div className="min-w-0 flex-1">
                    <p className="text-[14px] font-medium text-c-text">{u.name}</p>
                    <p className="text-[12.5px] text-c-text-3">{u.email} · {fill(copy.common.seen, { t: fmtAgo(u.last_seen_at) })}</p>
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
                <Row label={p.fields.sessionTimeout}>{p.values.sessionTimeout}</Row>
              </dl>
            </Panel>
            <Panel title={p.sections.retention}>
              <dl className="divide-y divide-c-border">
                <Row label={p.fields.retentionAudit}>{p.values.retentionAudit}</Row>
                <Row label={p.fields.retentionClaims}>{p.values.retentionClaims}</Row>
                <Row label={p.fields.retentionCrawl}>{p.values.retentionCrawl}</Row>
              </dl>
            </Panel>
          </div>
        </div>
      </DataState>
    </>
  );
}
