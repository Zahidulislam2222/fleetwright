"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { useEffect, useRef, useState } from "react";
import { ArrowLeft, Info, ShieldCheck } from "lucide-react";
import { FleetMark } from "@/components/brand/FleetMark";
import copy from "@/content/prototype.json";

const a = copy.auth;
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
    setEmail(String(form.get("email")));
    setStep("mfa");
  };

  const submitCode = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const code = String(new FormData(e.currentTarget).get("code") ?? "").replace(/\s/g, "");
    if (!/^\d{6}$/.test(code)) {
      setErrors({ code: a.errors.code });
      return;
    }
    router.push("/console");
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
              <Field id="password" name="password" type="password" label={a.password} autoComplete="current-password" error={errors.password} />
              <button type="submit" className="h-11 w-full rounded-lg bg-c-text text-[15px] font-semibold text-c-bg transition-opacity hover:opacity-90">
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
              <button type="submit" className="h-11 w-full rounded-lg bg-c-text text-[15px] font-semibold text-c-bg transition-opacity hover:opacity-90">
                {a.verify}
              </button>
              <p className="text-[12.5px] text-c-text-3">{a.lockoutNote}</p>
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
        <p className="mt-4 flex items-start gap-2 text-[12.5px] text-c-text-3">
          <Info aria-hidden className="mt-px size-4 shrink-0" /> {a.prototypeNote}
        </p>
      </main>
    </div>
  );
}
