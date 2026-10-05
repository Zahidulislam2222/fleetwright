"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { Play } from "lucide-react";
import type { DemoStatus, Session } from "@/mocks/types";
import copy from "@/content/console.json";
import config from "@/config/live.json";
import { apiSend, ApiError } from "@/lib/live/api";
import { useLiveGet } from "@/lib/live/useData";
import { fmtDuration } from "@/mocks/data";
import { fill } from "@/lib/fill";
import { Button, Panel } from "./ui";

const D = copy.live.demo;
type FieldKey = keyof typeof D.fields;

/**
 * Controls for the public demo tenant: start a capped burst of loads, or turn up adversity on the
 * mock board within the server's caps. The server enforces the caps and the role; it also puts
 * everything back to the calm preset on its own, so a visitor cannot leave the demo broken.
 */
export function DemoPanel({ session }: { session: Session }) {
  const status = useLiveGet<DemoStatus>("/v1/demo");
  const { reload } = status;
  const [draft, setDraft] = useState<Record<string, number | string>>({});
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");

  // The run countdown and the reset are server-side; refresh the panel a little faster than the page.
  useEffect(() => {
    const id = setInterval(reload, config.demoStatusPollMs);
    return () => clearInterval(id);
  }, [reload]);

  const s = status.data;
  if (!s) return null;
  const canControl = session.demo.can_control;

  const send = (method: "POST" | "PATCH", path: string, body?: unknown) => {
    setBusy(true);
    setMessage("");
    apiSend<DemoStatus>(method, path, body)
      .then(() => {
        setDraft({});
        setMessage(copy.live.saved);
      })
      .catch((err: unknown) => setMessage(fill(copy.live.failed, { detail: err instanceof ApiError ? err.message : String(err) })))
      .finally(() => {
        setBusy(false);
        reload();
      });
  };

  const value = (key: string) => draft[key] ?? s.adversity[key] ?? "";

  return (
    <Panel title={D.title} className="mb-4">
      <div className="grid gap-5 p-4 sm:p-5 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.4fr)]">
        <div className="space-y-3">
          <p className="text-[13.5px] leading-relaxed text-c-text-2">{D.intro}</p>
          <p className="font-mono text-[12.5px] text-c-text-3">{fill(D.feed, { n: s.feed_rate_per_min ?? copy.common.none })}</p>
          {canControl ? (
            <div className="flex flex-wrap items-center gap-3">
              <Button variant="primary" disabled={busy || s.run_active} onClick={() => send("POST", "/v1/demo/run")}>
                <Play aria-hidden className="size-4" /> {fill(D.run, { minutes: s.run_max_minutes })}
              </Button>
              {s.run_active && <span className="text-[13px] text-c-text-2" role="status">{fill(D.running, { t: fmtDuration(s.run_ends_in_s) })}</span>}
            </div>
          ) : (
            <p className="text-[13px] text-c-text-2">
              <Link href="/login" className="text-c-accent-text underline-offset-2 hover:underline">{copy.live.signIn}</Link> · {D.signInToControl}
            </p>
          )}
          <p className="text-[12px] text-c-text-3">{fill(D.resetNote, { t: fmtDuration(s.reset_after_s) })}</p>
        </div>

        <form
          aria-label={D.adversity}
          onSubmit={(e) => {
            e.preventDefault();
            if (Object.keys(draft).length) send("PATCH", "/v1/demo/adversity", { changes: draft });
          }}
          className="grid gap-3 sm:grid-cols-2"
        >
          {Object.entries(s.caps).map(([key, cap]) => {
            const label = D.fields[key as FieldKey] ?? key;
            const id = `demo-${key}`;
            return (
              <div key={key}>
                <label htmlFor={id} className="flex justify-between gap-2 text-[12.5px] text-c-text-2">
                  <span>{label}</span>
                  {cap.max != null && <span className="font-mono text-c-text-3">{fill(D.max, { n: cap.max })}</span>}
                </label>
                {cap.choices ? (
                  <select
                    id={id}
                    disabled={!canControl || busy}
                    value={String(value(key))}
                    onChange={(e) => setDraft((d) => ({ ...d, [key]: e.target.value }))}
                    className="mt-1 h-9 w-full rounded-lg border border-c-input-border bg-c-surface px-2.5 text-[13.5px] text-c-text"
                  >
                    {cap.choices.map((c) => (
                      <option key={c} value={c}>{c}</option>
                    ))}
                  </select>
                ) : (
                  <input
                    id={id}
                    type="number"
                    min={0}
                    max={cap.max ?? undefined}
                    step={cap.max != null && cap.max <= 1 ? 0.05 : 50}
                    disabled={!canControl || busy}
                    value={value(key)}
                    onChange={(e) => setDraft((d) => ({ ...d, [key]: Number(e.target.value) }))}
                    className="mt-1 h-9 w-full rounded-lg border border-c-input-border bg-c-surface px-3 text-[13.5px] text-c-text tabular"
                  />
                )}
              </div>
            );
          })}
          {canControl && (
            <div className="flex flex-wrap items-center gap-3 sm:col-span-2">
              <Button type="submit" disabled={busy || !Object.keys(draft).length}>{D.apply}</Button>
              {message && <p role="status" className="text-[13px] text-c-text-2">{message}</p>}
            </div>
          )}
        </form>
      </div>
    </Panel>
  );
}
