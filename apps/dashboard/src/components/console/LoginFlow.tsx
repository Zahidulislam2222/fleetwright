"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Info, ShieldCheck, Sparkles } from "lucide-react";
import { FleetMark } from "@/components/brand/FleetMark";
import copy from "@/content/prototype.json";
import type { DemoHint, MfaResult } from "@/mocks/types";
import { apiGet, apiSend, ApiError } from "@/lib/live/api";
import { refreshSession, useLive } from "@/lib/live/store";
import { fill } from "@/lib/fill";

const a = copy.auth;

function liveError(err: unknown): string {
  if (err instanceof ApiError) {
    if (err.status === 429) return fill(a.errors.locked, { minutes: Math.max(1, Math.ceil((err.retryAfterS ?? 60) / 60)) });
    if (err.status === 401) return a.errors.wrong;
    if (err.status === 422) return a.errors.wrong;
  }
  return a.errors.network;
}

/** The shared demo login, published by the API on purpose (role `demo`: capped controls only). */
function DemoHintBox({ hint, onFill }: { hint: DemoHint; onFill: () => void }) {
  return (
    <section aria-labelledby="demo-hint-title" className="mt-4 rounded-2xl border border-c-border bg-c-surface p-5 text-[13.5px]">
      <h2 id="demo-hint-title" className="flex items-center gap-2 font-semibold text-c-text">
        <Sparkles aria-hidden className="size-4 text-c-accent-text" /> {a.demo.title}
      </h2>
      <p className="mt-1 text-c-text-2">{a.demo.body}</p>
      <dl className="mt-3 grid grid-cols-[auto_minmax(0,1fr)] gap-x-3 gap-y-1 font-mono text-[12.5px]">
        <dt className="text-c-text-3">{a.demo.email}</dt>
        <dd className="truncate text-c-text">{hint.email}</dd>
        <dt className="text-c-text-3">{a.demo.password}</dt>
        <dd className="break-all text-c-text">{hint.password}</dd>
        <dt className="text-c-text-3">{a.demo.code}</dt>
        <dd className="tracking-[0.2em] text-c-text">{hint.code}</dd>
      </dl>
      <button type="button" onClick={onFill} className="mt-3 h-9 rounded-lg border border-c-border px-3 text-[13px] text-c-text hover:bg-c-surface-2">
        {a.demo.fill}
      </button>
    </section>
  );
}
const EMAIL = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function Field({
  id,
  label,
  error,
  className = "",
  ...input
}: React.ComponentProps<"input"> & { id: string; label: string; error?: string }) {
  return (
    <div>
      <label htmlFor={id} className="block text-[13.5px] font-medium text-c-text">{label}</label>
      <input
        id={id}
        {...input}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`mt-1.5 h-11 w-full rounded-lg border bg-c-surface px-3 text-[15px] text-c-text ${error ? "border-c-bad" : "border-c-input-border"} ${className}`}
      />
      {error && <p id={`${id}-error`} className="mt-1.5 text-[13px] text-c-bad">{error}</p>}
    </div>
  );
}

export function LoginFlow() {
  const router = useRouter();
  const { mode, session } = useLive();
  const live = mode === "live";
  const [hint, setHint] = useState<DemoHint | null>(null);
  const [busy, setBusy] = useState(false);
  const passwordRef = useRef<HTMLInputElement>(null);
  const [step, setStep] = useState<"password" | "mfa">("password");
  const [email, setEmail] = useState("");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const codeRef = useRef<HTMLInputElement>(null);
  const emailRef = useRef<HTMLInputElement>(null);
  const [returned, setReturned] = useState(false);

  useEffect(() => {
    if (step === "mfa") codeRef.current?.focus();
    else if (returned) emailRef.current?.focus();
  }, [step, returned]);

  // The demo hint carries the current code, so fetch it again for the code step.
  useEffect(() => {
    if (!live) return;
    const ctrl = new AbortController();
    apiGet<DemoHint>("/v1/auth/demo-hint", ctrl.signal)
      .then(setHint)
      .catch(() => setHint(null));
    return () => ctrl.abort();
  }, [live, step]);

  // Move focus to the first invalid field so the error is announced and fixable.
  useEffect(() => {
    const first = Object.keys(errors)[0];
    if (first) document.getElementById(first)?.focus();
  }, [errors]);

  const submitPassword = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    const next: Record<string, string> = {};
    if (!EMAIL.test(String(form.get("email") ?? ""))) next.email = a.errors.email;
    if (!String(form.get("password") ?? "")) next.password = a.errors.password;
    setErrors(next);
    if (Object.keys(next).length) return;
    // The password is never kept in state: the form field is the only holder, discarded on step change.
    const typed = String(form.get("email"));
    if (!live) {
      setEmail(typed);
      setStep("mfa");
      return;
    }
    setBusy(true);
    apiSend("POST", "/v1/auth/login", { email: typed, password: String(form.get("password")) })
      .then(() => {
        setEmail(typed);
        setStep("mfa");
      })
      .catch((err: unknown) => setErrors({ password: liveError(err) }))
      .finally(() => setBusy(false));
  };

  const submitCode = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const code = String(new FormData(e.currentTarget).get("code") ?? "").replace(/\s/g, "");
    if (!/^\d{6}$/.test(code)) {
      setErrors({ code: a.errors.code });
      return;
    }
    if (!live) {
      router.push("/console");
      return;
    }
    setBusy(true);
    apiSend<MfaResult>("POST", "/v1/auth/mfa", { code })
      .then(async () => {
        await refreshSession();
        router.push("/console");
      })
      .catch((err: unknown) => setErrors({ code: liveError(err) }))
      .finally(() => setBusy(false));
  };

  const fillDemo = () => {
    if (!hint) return;
    if (step === "password") {
      if (emailRef.current) emailRef.current.value = hint.email;
      if (passwordRef.current) passwordRef.current.value = hint.password;
    } else if (codeRef.current) {
      codeRef.current.value = hint.code;
    }
  };

  return (
    <div className="console-theme grid min-h-svh place-items-center bg-c-bg px-4 py-10 text-c-text">
      <main className="w-full max-w-[400px]">
        <Link href="/" className="mb-8 inline-flex items-center gap-2.5 rounded-lg">
          <span className="grid size-9 place-items-center rounded-full bg-c-text text-c-bg">
            <FleetMark className="size-[18px]" />
          </span>
          <span className="font-pixel text-[20px]">{a.brand}</span>
        </Link>
        <div className="rounded-2xl border border-c-border bg-c-surface p-6 shadow-[var(--c-shadow)] sm:p-7">
          {step === "password" ? (
            <form noValidate onSubmit={submitPassword} className="space-y-4">
              <div>
                <h1 className="text-[22px] font-semibold tracking-[-0.02em]">{a.title}</h1>
                <p className="mt-1 text-[14px] text-c-text-2">{a.subtitle}</p>
              </div>
              <Field ref={emailRef} id="email" name="email" type="email" label={a.email} autoComplete="username" inputMode="email" defaultValue={email} error={errors.email} />
              <Field ref={passwordRef} id="password" name="password" type="password" label={a.password} autoComplete="current-password" error={errors.password} />
              <button type="submit" disabled={busy} aria-busy={busy} className="disabled:opacity-60 h-11 w-full rounded-lg bg-c-text text-[15px] font-semibold text-c-bg transition-opacity hover:opacity-90">
                {a.submit}
              </button>
            </form>
          ) : (
            <form noValidate onSubmit={submitCode} className="space-y-4">
              <span className="grid size-10 place-items-center rounded-full bg-c-ok-bg text-c-ok">
                <ShieldCheck aria-hidden className="size-5" />
              </span>
              <div>
                <h1 className="text-[22px] font-semibold tracking-[-0.02em]">{a.mfaTitle}</h1>
                <p className="mt-1 text-[14px] text-c-text-2">{a.mfaSubtitle}</p>
                <p className="mt-1 font-mono text-[12.5px] text-c-text-3">{email}</p>
              </div>
              <Field
                ref={codeRef}
                id="code"
                name="code"
                label={a.code}
                inputMode="numeric"
                autoComplete="one-time-code"
                maxLength={7}
                pattern="\d{6}"
                className="tracking-[0.4em]"
                error={errors.code}
              />
              <button type="submit" disabled={busy} aria-busy={busy} className="h-11 w-full rounded-lg bg-c-text text-[15px] font-semibold text-c-bg transition-opacity hover:opacity-90 disabled:opacity-60">
                {a.verify}
              </button>
              {!live && <p className="text-[12.5px] text-c-text-3">{a.lockoutNote}</p>}
              <button
                type="button"
                onClick={() => {
                  setErrors({});
                  setReturned(true);
                  setStep("password");
                }}
                className="inline-flex items-center gap-1.5 rounded text-[13.5px] text-c-text-2 hover:text-c-text"
              >
                <ArrowLeft aria-hidden className="size-4" /> {a.back}
              </button>
            </form>
          )}
        </div>
        {live && hint && <DemoHintBox hint={hint} onFill={fillDemo} />}
        <p className="mt-4 flex items-start gap-2 text-[12.5px] text-c-text-3">
          <Info aria-hidden className="mt-px size-4 shrink-0" /> {live ? a.liveNote : a.prototypeNote}
        </p>
        {live && session && !session.authenticated && (
          <p className="mt-3 text-[13px]">
            <Link href="/console" className="text-c-accent-text underline-offset-2 hover:underline">{a.browse}</Link>
          </p>
        )}
      </main>
    </div>
  );
}
