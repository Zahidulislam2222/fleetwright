"use client";

import { useCallback, useEffect, useId, useRef, useState } from "react";
import { ExternalLink, MessageCircleQuestionMark, RotateCcw, Send, Sparkles, Square, ThumbsDown, ThumbsUp, X } from "lucide-react";
import copy from "@/content/console.json";
import config from "@/config/live.json";
import type { AssistantAnswer, AssistantInfo } from "@/mocks/types";
import { ApiError, apiGet, apiSend } from "@/lib/live/api";
import { useLive } from "@/lib/live/store";
import { useDialog } from "@/lib/useDialog";
import { fill } from "@/lib/fill";
import { Badge, Button } from "./ui";

const A = copy.assistant;
/** /v1 contract bounds (AskIn / Turn in contracts/openapi.yaml). */
const TURN_MAX_CHARS = 4000;
const HISTORY_MAX_TURNS = 20;

type Turn = { role: "user" | "assistant"; content: string };

/**
 * The most recent turns that fit the server's history limits and keep the whole request body (UTF-8
 * bytes, not characters) under the API body limit. The server bounds them again.
 */
function historyFor(entries: Entry[], question: string, info: AssistantInfo): Turn[] {
  const turns: Turn[] = [];
  for (const e of entries) {
    if (e.kind === "user") turns.push({ role: "user", content: e.text });
    else if (e.kind === "answer") turns.push({ role: "assistant", content: e.answer.answer });
  }
  const enc = new TextEncoder();
  let bytes = enc.encode(JSON.stringify({ question, history: [] })).length;
  let chars = 0;
  const kept: Turn[] = [];
  const keep = Math.min(info.max_history_turns, HISTORY_MAX_TURNS);
  if (keep <= 0) return []; // slice(-0) would return every turn
  for (const t of turns.slice(-keep).reverse()) {
    const content = t.content.slice(0, Math.min(TURN_MAX_CHARS, info.max_history_chars - chars));
    if (!content) break;
    const turn = { role: t.role, content };
    const size = enc.encode(JSON.stringify(turn)).length + 1;
    if (bytes + size > config.assistantRequestBytes) break;
    bytes += size;
    chars += content.length;
    kept.push(turn);
  }
  return kept.reverse();
}

type Entry =
  | { kind: "user"; text: string }
  | { kind: "answer"; answer: AssistantAnswer; vote?: boolean }
  | { kind: "note"; text: string };

/**
 * The console help assistant (global Rule 24): a side panel that answers from the published docs and
 * the read-only data this role can already see. Answers are plain text (never HTML), marked as
 * AI-generated in a machine-readable attribute, and the console stays fully usable without it.
 * The conversation lives only in this page's memory; "New conversation" forgets it.
 */
export function AssistantButton() {
  const { mode } = useLive();
  const [open, setOpen] = useState(false);
  const [entries, setEntries] = useState<Entry[]>([]);
  const close = useCallback(() => setOpen(false), []);
  if (mode === "checking") return null;
  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-haspopup="dialog"
        aria-expanded={open}
        aria-label={A.openLabel}
        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-c-border bg-c-surface px-3 text-[13px] text-c-text hover:bg-c-surface-2"
      >
        <MessageCircleQuestionMark aria-hidden className="size-4" />
        <span className="hidden sm:inline">{A.open}</span>
      </button>
      {open && <AssistantPanel onClose={close} entries={entries} setEntries={setEntries} />}
    </>
  );
}

function AssistantPanel({
  onClose,
  entries,
  setEntries,
}: {
  onClose: () => void;
  entries: Entry[];
  setEntries: React.Dispatch<React.SetStateAction<Entry[]>>;
}) {
  const { mode } = useLive();
  const live = mode === "live";
  const ref = useRef<HTMLDivElement>(null);
  const listRef = useRef<HTMLDivElement>(null);
  const titleId = useId();
  const inputId = useId();
  const [info, setInfo] = useState<AssistantInfo | null>(null);
  const [infoFailed, setInfoFailed] = useState(false);
  const [question, setQuestion] = useState("");
  const [pending, setPending] = useState<AbortController | null>(null);
  const [status, setStatus] = useState("");
  const inputRef = useRef<HTMLTextAreaElement>(null);
  /** Set when "New conversation" aborts a question, so its abort does not land in the new chat. */
  const discarded = useRef<AbortController | null>(null);
  useDialog(ref, onClose);

  useEffect(() => {
    if (!live) return;
    const ctrl = new AbortController();
    apiGet<AssistantInfo>("/v1/assistant", ctrl.signal)
      .then(setInfo)
      .catch((err: unknown) => {
        if (!(err instanceof DOMException && err.name === "AbortError")) setInfoFailed(true);
      });
    return () => ctrl.abort();
  }, [live]);

  useEffect(() => {
    listRef.current?.scrollTo({ top: listRef.current.scrollHeight });
  }, [entries, pending]);

  useEffect(() => () => pending?.abort(), [pending]);

  const max = info?.max_question_chars;

  const ask = useCallback(
    async (text: string) => {
      const q = text.trim();
      if (!q || pending || !info) return;
      if (q.length > info.max_question_chars) {
        setEntries((e) => [...e, { kind: "note", text: fill(A.tooLong, { n: info.max_question_chars }) }]);
        return;
      }
      const history = historyFor(entries, q, info);
      const ctrl = new AbortController();
      setPending(ctrl);
      setStatus(A.thinking);
      setQuestion("");
      setEntries((e) => [...e, { kind: "user", text: q }]);
      try {
        const answer = await apiSend<AssistantAnswer>("POST", "/v1/assistant/ask", { question: q, history }, ctrl.signal);
        if (discarded.current === ctrl) return;
        setEntries((e) => [...e, { kind: "answer", answer }]);
        // Screen readers hear the answer itself, not only that one arrived.
        setStatus(`${answer.ai_generated ? A.aiGenerated : A.searchResult}: ${answer.answer}`);
      } catch (err) {
        if (discarded.current === ctrl) return;
        if (err instanceof DOMException && err.name === "AbortError") {
          setEntries((e) => [...e, { kind: "note", text: A.stopped }]);
          setStatus(A.stopped);
        } else {
          const detail = err instanceof ApiError ? err.message : String(err);
          setEntries((e) => [...e, { kind: "note", text: fill(A.failed, { detail }) }]);
          setStatus(fill(A.failed, { detail }));
        }
      } finally {
        setPending((p) => (p === ctrl ? null : p));
        // The Send/Stop button swap would otherwise drop keyboard focus to the page.
        if (discarded.current !== ctrl) inputRef.current?.focus();
      }
    },
    [entries, info, pending, setEntries],
  );

  const vote = useCallback(
    (index: number, helpful: boolean) => {
      const entry = entries[index];
      if (entry?.kind !== "answer" || entry.vote !== undefined) return;
      setEntries((e) => e.map((x, i) => (i === index && x.kind === "answer" ? { ...x, vote: helpful } : x)));
      apiSend("POST", "/v1/assistant/feedback", { id: entry.answer.id, helpful }).catch(() => undefined);
    },
    [entries, setEntries],
  );

  const ready = live && info !== null;
  const unavailable = live && infoFailed;

  return (
    <div className="fixed inset-0 z-[var(--z-overlay)]">
      <button aria-label={A.close} tabIndex={-1} className="absolute inset-0 bg-black/40" onClick={onClose} />
      <div
        ref={ref}
        role="dialog"
        aria-modal="true"
        aria-labelledby={titleId}
        className="absolute inset-y-0 right-0 flex w-full flex-col border-l border-c-border bg-c-surface shadow-2xl sm:w-[min(440px,92vw)]"
      >
        <div className="flex items-center gap-2 border-b border-c-border px-4 py-3">
          <Sparkles aria-hidden className="size-4 text-c-accent-text" />
          <h2 id={titleId} className="text-[15px] font-semibold text-c-text">{A.title}</h2>
          <Badge tone="info">{A.aiBadge}</Badge>
          <div className="ml-auto flex items-center gap-1">
            {entries.length > 0 && (
              <Button variant="ghost" onClick={() => {
                  discarded.current = pending;
                  pending?.abort();
                  setPending(null);
                  setEntries([]);
                  setStatus(A.newChat);
                  inputRef.current?.focus();
                }} aria-label={A.newChat} title={A.newChat}>
                <RotateCcw aria-hidden className="size-4" />
              </Button>
            )}
            <button onClick={onClose} aria-label={A.close} className="grid size-9 place-items-center rounded-lg text-c-text-2 hover:bg-c-surface-2">
              <X aria-hidden className="size-5" />
            </button>
          </div>
        </div>

        <div ref={listRef} className="flex-1 space-y-4 overflow-y-auto px-4 py-4">
          {!live && <p className="rounded-xl bg-c-surface-2 p-3 text-[13.5px] leading-relaxed text-c-text-2">{A.prototype}</p>}
          {unavailable && <p className="rounded-xl bg-c-warn-bg p-3 text-[13.5px] leading-relaxed text-c-warn">{A.unavailable}</p>}
          {ready && (
            <div className="space-y-3">
              <p className="rounded-xl border border-c-border bg-c-surface-2 p-3 text-[13px] leading-relaxed text-c-text-2">{info.disclosure}</p>
              {!info.enabled && <p className="rounded-xl bg-c-warn-bg p-3 text-[13px] leading-relaxed text-c-warn">{A.aiOff}</p>}
              {entries.length === 0 && (
                <div>
                  <p className="text-[13.5px] text-c-text-2">{A.intro}</p>
                  <p className="mt-3 font-mono text-[11px] uppercase tracking-[0.14em] text-c-text-3">{A.suggestionsLabel}</p>
                  <ul className="mt-2 flex flex-col gap-1.5">
                    {info.suggestions.map((s) => (
                      <li key={s}>
                        <button
                          type="button"
                          onClick={() => void ask(s)}
                          className="w-full rounded-lg border border-c-border px-3 py-2 text-left text-[13.5px] text-c-text hover:bg-c-surface-2"
                        >
                          {s}
                        </button>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
          )}
          {entries.map((e, i) =>
            e.kind === "user" ? (
              <div key={i} className="ml-8 rounded-xl bg-c-surface-3 px-3 py-2 text-[14px] text-c-text">
                <span className="sr-only">{A.you}: </span>
                <p className="whitespace-pre-wrap break-words">{e.text}</p>
              </div>
            ) : e.kind === "note" ? (
              <p key={i} className="rounded-xl bg-c-warn-bg px-3 py-2 text-[13px] text-c-warn">{e.text}</p>
            ) : (
              <AnswerCard key={i} answer={e.answer} vote={e.vote} onVote={(h) => vote(i, h)} />
            ),
          )}
          {pending && (
            <p className="flex items-center gap-2 text-[13px] text-c-text-3">
              <span className="inline-block size-2 animate-pulse rounded-full bg-c-accent motion-reduce:animate-none" aria-hidden />
              {A.thinking}
            </p>
          )}
        </div>
        <div role="status" aria-live="polite" className="sr-only">{status}</div>

        <form
          className="border-t border-c-border px-4 py-3"
          onSubmit={(ev) => {
            ev.preventDefault();
            void ask(question);
          }}
        >
          <label htmlFor={inputId} className="sr-only">{A.inputLabel}</label>
          <textarea
            id={inputId}
            ref={inputRef}
            value={question}
            onChange={(ev) => setQuestion(ev.target.value)}
            onKeyDown={(ev) => {
              if (ev.key === "Enter" && !ev.shiftKey && !ev.nativeEvent.isComposing) {
                ev.preventDefault();
                void ask(question);
              }
            }}
            rows={2}
            maxLength={max}
            disabled={!ready}
            placeholder={A.placeholder}
            className="w-full resize-none rounded-lg border border-c-input-border bg-c-surface px-3 py-2 text-[14px] text-c-text placeholder:text-c-text-3 disabled:opacity-60"
          />
          <div className="mt-2 flex items-center gap-2">
            <span className="font-mono text-[11px] text-c-text-3" aria-hidden>{max !== undefined && fill(A.counter, { n: question.length, max })}</span>
            {info?.contact && (
              <a href={info.contact.url} target="_blank" rel="noopener noreferrer" className="truncate text-[12px] text-c-text-2 underline underline-offset-2 hover:text-c-text">
                {info.contact.label}
              </a>
            )}
            <div className="ml-auto">
              {pending ? (
                <Button type="button" onClick={() => pending.abort()}>
                  <Square aria-hidden className="size-3.5" />
                  {A.stop}
                </Button>
              ) : (
                <Button type="submit" variant="primary" disabled={!ready || !question.trim()}>
                  <Send aria-hidden className="size-3.5" />
                  {A.send}
                </Button>
              )}
            </div>
          </div>
          {info?.today && (
            <p className="mt-2 font-mono text-[11px] text-c-text-3">
              {fill(A.today, {
                questions: info.today.questions ?? 0,
                ai: info.today.ai ?? 0,
                search: info.today.search ?? 0,
                cost: ((info.today.cost_micro ?? 0) / 1_000_000).toFixed(4),
              })}
            </p>
          )}
        </form>
      </div>
    </div>
  );
}

function AnswerCard({ answer, vote, onVote }: { answer: AssistantAnswer; vote?: boolean; onVote: (helpful: boolean) => void }) {
  return (
    <article
      data-ai-generated={answer.ai_generated ? "true" : "false"}
      aria-label={answer.ai_generated ? A.aiGenerated : A.searchResult}
      className="mr-4 space-y-2 rounded-xl border border-c-border px-3 py-2.5"
    >
      <div className="flex items-center gap-2 text-[11.5px] text-c-text-3">
        <Sparkles aria-hidden className="size-3.5" />
        {answer.ai_generated ? A.aiGenerated : A.searchResult}
      </div>
      {answer.notice && <p className="rounded-lg bg-c-warn-bg px-2.5 py-1.5 text-[12.5px] text-c-warn">{answer.notice}</p>}
      <p className="whitespace-pre-wrap break-words text-[14px] leading-relaxed text-c-text">{answer.answer}</p>
      {answer.used_tools.length > 0 && (
        <p className="text-[12px] text-c-text-3">{fill(A.usedData, { tools: answer.used_tools.join(", ") })}</p>
      )}
      {answer.sources.length > 0 && (
        <div>
          <p className="font-mono text-[10.5px] uppercase tracking-[0.14em] text-c-text-3">{A.sources}</p>
          <ul className="mt-1 space-y-0.5">
            {answer.sources.map((s) => (
              <li key={s.path + s.title} className="text-[12.5px]">
                {s.url ? (
                  <a href={s.url} target="_blank" rel="noopener noreferrer" className="inline-flex items-center gap-1 text-c-info underline underline-offset-2">
                    {s.title}
                    <ExternalLink aria-hidden className="size-3" />
                  </a>
                ) : (
                  <span className="text-c-text-2">{s.title}</span>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex items-center gap-1">
        {vote === undefined ? (
          <>
            <button type="button" onClick={() => onVote(true)} aria-label={A.helpful} title={A.helpful} className="grid size-8 place-items-center rounded-md text-c-text-3 hover:bg-c-surface-2 hover:text-c-text">
              <ThumbsUp aria-hidden className="size-3.5" />
            </button>
            <button type="button" onClick={() => onVote(false)} aria-label={A.notHelpful} title={A.notHelpful} className="grid size-8 place-items-center rounded-md text-c-text-3 hover:bg-c-surface-2 hover:text-c-text">
              <ThumbsDown aria-hidden className="size-3.5" />
            </button>
          </>
        ) : (
          <p className="text-[12px] text-c-text-3">{A.thanks}</p>
        )}
      </div>
    </article>
  );
}
