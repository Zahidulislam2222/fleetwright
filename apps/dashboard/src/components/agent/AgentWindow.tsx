"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { ArrowLeft, Bot, Check, CircleCheck, Hourglass, Send, ShieldAlert, UserRound, X } from "lucide-react";
import { FleetMark } from "@/components/brand/FleetMark";
import { Badge, Button, Panel } from "@/components/console/ui";
import copy from "@/content/prototype.json";
import { fill } from "@/lib/fill";

const a = copy.agent;
type Decision = "pending" | "approved" | "rejected";
type Message = { role: string; text: string };
type Step = { status: string; text: string; at: string; flag?: boolean; approval?: string };

export function AgentWindow() {
  const [messages, setMessages] = useState<Message[]>(a.messages);
  const [steps, setSteps] = useState<Step[]>(a.steps);
  const [draft, setDraft] = useState("");
  const [decisions, setDecisions] = useState<Record<string, Decision>>({});
  const [lastDecided, setLastDecided] = useState<string | null>(null);

  // The Approve/Reject buttons disappear after a decision; keep focus on the decided item.
  useEffect(() => {
    if (lastDecided) document.getElementById(`approval-${lastDecided}`)?.focus();
  }, [lastDecided]);

  const decide = (id: string, action: string, d: Decision) => {
    setDecisions((x) => ({ ...x, [id]: d }));
    setLastDecided(id);
    setSteps((s) => [
      ...s.map((st) => (st.status === "waiting" && st.approval === id ? { ...st, status: "done" } : st)),
      { status: "done", text: fill(a.decisionLog, { action, decision: d === "approved" ? a.approved : a.rejected }), at: a.decisionAt },
    ]);
  };

  const send = (e: React.FormEvent) => {
    e.preventDefault();
    const text = draft.trim();
    if (!text) return;
    setMessages((m) => [...m, { role: "user", text }, { role: "agent", text: a.scriptedReply }]);
    setDraft("");
  };

  return (
    <div className="console-theme min-h-svh bg-c-bg text-c-text">
      <header className="flex flex-wrap items-center gap-3 border-b border-c-border px-4 py-3 lg:px-8">
        <Link href="/console" className="inline-flex items-center gap-2 rounded-lg text-[13.5px] text-c-text-2 hover:text-c-text">
          <ArrowLeft aria-hidden className="size-4" /> {a.backToConsole}
        </Link>
        <span className="mx-1 h-5 w-px bg-c-border" aria-hidden />
        <span className="grid size-8 place-items-center rounded-full bg-c-text text-c-bg">
          <FleetMark className="size-4" />
        </span>
        <div className="min-w-0">
          <h1 className="text-[16px] font-semibold leading-tight">{a.title}</h1>
          <p className="truncate text-[12.5px] text-c-text-3">{a.subtitle}</p>
        </div>
        <p className="ml-auto rounded-full border border-c-border px-3 py-1 font-mono text-[11.5px] text-c-text-2">{a.prototypeNote}</p>
      </header>

      <main className="mx-auto grid max-w-[1400px] gap-4 p-4 lg:grid-cols-[minmax(0,1.15fr)_minmax(0,1fr)] lg:p-8">
        <Panel title={a.chatTitle} aside={<span className="text-[12px] text-c-text-3">{a.model}</span>} className="flex min-h-[520px] flex-col">
          <ol aria-live="polite" className="flex-1 space-y-4 overflow-y-auto p-4 sm:p-5">
            {messages.map((m, i) => (
              <li key={i} className={`flex gap-3 ${m.role === "user" ? "flex-row-reverse" : ""}`}>
                <span className={`grid size-8 shrink-0 place-items-center rounded-full ${m.role === "user" ? "bg-c-surface-3" : "bg-c-accent text-c-on-accent"}`}>
                  {m.role === "user" ? <UserRound aria-hidden className="size-4" /> : <Bot aria-hidden className="size-4" />}
                </span>
                <p className={`max-w-[75%] rounded-2xl px-4 py-2.5 text-[14px] leading-relaxed ${m.role === "user" ? "bg-c-text text-c-bg" : "bg-c-surface-2 text-c-text"}`}>
                  <span className="sr-only">{m.role === "user" ? a.you : a.agentPrefix}</span>
                  {m.text}
                </p>
              </li>
            ))}
          </ol>
          <form onSubmit={send} className="flex gap-2 border-t border-c-border p-3">
            <label htmlFor="agent-composer" className="sr-only">{a.composerLabel}</label>
            <input
              id="agent-composer"
              value={draft}
              onChange={(e) => setDraft(e.target.value)}
              maxLength={500}
              placeholder={a.composerPlaceholder}
              className="h-10 min-w-0 flex-1 rounded-lg border border-c-input-border bg-c-surface px-3 text-[14px] text-c-text placeholder:text-c-text-3"
            />
            <Button type="submit" variant="primary" className="h-10" aria-disabled={!draft.trim()}>
              <Send aria-hidden className="size-4" /> {a.send}
            </Button>
          </form>
        </Panel>

        <div className="grid content-start gap-4">
          <Panel title={a.queueTitle}>
            <ul className="divide-y divide-c-border">
              {a.queue.map((q) => {
                const d = decisions[q.id] ?? "pending";
                return (
                  <li key={q.id} id={`approval-${q.id}`} tabIndex={-1} className="p-4 outline-none focus-visible:bg-c-surface-2 sm:p-5">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <p className="text-[14px] font-semibold">{q.action} <span className="font-normal text-c-text-2">→ {q.target}</span></p>
                      {d === "pending" ? (
                        <Badge tone="warn" icon={Hourglass}>{a.pending}</Badge>
                      ) : d === "approved" ? (
                        <Badge tone="ok">{a.approved}</Badge>
                      ) : (
                        <Badge tone="bad">{a.rejected}</Badge>
                      )}
                    </div>
                    <p className="mt-1 text-[12.5px] text-c-text-3">{q.risk}</p>
                    <blockquote className="mt-3 rounded-lg border border-c-border bg-c-surface-2 px-3 py-2 text-[13.5px] text-c-text-2">{q.preview}</blockquote>
                    {d === "pending" && (
                      <div className="mt-3 flex gap-2">
                        <Button variant="primary" onClick={() => decide(q.id, q.action, "approved")}>
                          <Check aria-hidden className="size-4" /> {a.approve}
                        </Button>
                        <Button onClick={() => decide(q.id, q.action, "rejected")}>
                          <X aria-hidden className="size-4" /> {a.reject}
                        </Button>
                      </div>
                    )}
                  </li>
                );
              })}
            </ul>
            <p className="flex items-start gap-2 border-t border-c-border px-4 py-3 text-[12.5px] text-c-text-3 sm:px-5">
              <ShieldAlert aria-hidden className="mt-px size-4 shrink-0" /> {a.untrustedNote}
            </p>
          </Panel>

          <Panel title={a.logTitle}>
            <ol className="space-y-3 p-4 sm:p-5">
              {steps.map((s, i) => (
                <li key={i} className="flex gap-3 text-[13.5px]">
                  {s.status === "waiting" ? (
                    <Hourglass aria-label={a.stepStatus.waiting} className="mt-0.5 size-4 shrink-0 text-c-warn" />
                  ) : s.flag ? (
                    <ShieldAlert aria-label={a.stepStatus.blocked} className="mt-0.5 size-4 shrink-0 text-c-bad" />
                  ) : (
                    <CircleCheck aria-label={a.stepStatus.done} className="mt-0.5 size-4 shrink-0 text-c-ok" />
                  )}
                  <span className={`flex-1 ${s.flag ? "text-c-text" : "text-c-text-2"}`}>{s.text}</span>
                  <span className="font-mono text-[12px] text-c-text-3">{s.at}</span>
                </li>
              ))}
            </ol>
          </Panel>
        </div>
      </main>
    </div>
  );
}
