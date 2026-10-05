"use client";

import Link from "next/link";
import { useCallback, useEffect, useRef, useState } from "react";
import { useDialog } from "@/lib/useDialog";
import { CircleCheck, CircleX, Info, LogOut, Truck } from "lucide-react";
import { boardLoads, fmtAgo, fmtUsd, type BoardLoad } from "@/mocks/data";
import copy from "@/content/prototype.json";
import { fill } from "@/lib/fill";

const b = copy.board;
type Step = "signin" | "otp" | "feed";
type Booking = { load: BoardLoad; stage: "confirm" | "captcha" | "success" | "taken" } | null;

function Input({ id, label, error, ...rest }: React.ComponentProps<"input"> & { id: string; label: string; error?: string }) {
  return (
    <div>
      <label htmlFor={id} className="block text-[13.5px] font-medium text-b-text">{label}</label>
      <input
        id={id}
        {...rest}
        aria-invalid={error ? true : undefined}
        aria-describedby={error ? `${id}-error` : undefined}
        className={`mt-1 h-10 w-full rounded border bg-b-surface px-3 text-[15px] text-b-text ${error ? "border-b-bad" : "border-b-input-border"}`}
      />
      {error && <p id={`${id}-error`} className="mt-1 text-[13px] text-b-bad">{error}</p>}
    </div>
  );
}

function BrandButton(props: React.ButtonHTMLAttributes<HTMLButtonElement>) {
  return <button {...props} className={`h-10 rounded bg-b-brand px-4 text-[14.5px] font-semibold text-b-brand-text hover:opacity-90 disabled:opacity-50 ${props.className ?? ""}`} />;
}

function Dialog({ labelledBy, onClose, stage, fallbackFocus, children }: { labelledBy: string; onClose: () => void; stage: string; fallbackFocus: () => HTMLElement | null; children: React.ReactNode }) {
  const ref = useRef<HTMLDivElement>(null);
  useDialog(ref, onClose, stage, fallbackFocus);
  return (
    <div className="fixed inset-0 z-[var(--z-overlay)] grid place-items-center bg-black/40 p-4">
      <div ref={ref} role="dialog" aria-modal="true" aria-labelledby={labelledBy} className="w-full max-w-[420px] rounded-lg border border-b-border bg-b-surface p-6 shadow-2xl">
        {children}
      </div>
    </div>
  );
}

export function MockBoard() {
  const [step, setStep] = useState<Step>("signin");
  const [errors, setErrors] = useState<Record<string, string>>({});
  const [booking, setBooking] = useState<Booking>(null);
  const [status, setStatus] = useState<Record<string, "booked" | "taken">>({});
  const [human, setHuman] = useState(false);
  const loads = boardLoads();

  useEffect(() => {
    const first = Object.keys(errors)[0];
    if (first) document.getElementById(first === "password" ? "board-password" : first)?.focus();
  }, [errors]);
  const close = useCallback(() => setBooking(null), []);
  const lastLoad = booking?.load.id;
  const focusRowStatus = useCallback(() => (lastLoad ? document.getElementById(`status-${lastLoad}`) : null), [lastLoad]);

  const signIn = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const f = new FormData(e.currentTarget);
    const next: Record<string, string> = {};
    if (!String(f.get("username") ?? "").trim()) next.username = b.errors.username;
    if (!String(f.get("password") ?? "")) next.password = b.errors.password;
    setErrors(next);
    if (!Object.keys(next).length) setStep("otp");
  };

  const verify = (e: React.FormEvent<HTMLFormElement>) => {
    e.preventDefault();
    const code = String(new FormData(e.currentTarget).get("otp") ?? "").trim();
    if (!/^\d{6}$/.test(code)) return setErrors({ otp: b.errors.otp });
    setErrors({});
    setStep("feed");
  };

  const finish = () => {
    if (!booking) return;
    const result = booking.load.contested ? "taken" : "success";
    setStatus((s) => ({ ...s, [booking.load.id]: result === "taken" ? "taken" : "booked" }));
    setBooking({ load: booking.load, stage: result });
    setHuman(false);
  };

  const ref = booking ? fill(b.refFormat, { id: booking.load.id.slice(3), suffix: String(booking.load.rate_usd).slice(-3) }) : "";

  return (
    <div className="board-theme min-h-svh bg-b-bg text-b-text">
      <header className="border-b border-b-border bg-b-surface">
        <div className="mx-auto flex max-w-[1100px] flex-wrap items-center gap-3 px-4 py-3">
          <span className="grid size-8 place-items-center rounded bg-b-brand text-b-brand-text">
            <Truck aria-hidden className="size-4" />
          </span>
          <div className="min-w-0">
            <p className="text-[16px] font-bold leading-tight">{b.name}</p>
            <p className="text-[12px] text-b-text-2">{b.tagline}</p>
          </div>
          <div className="ml-auto flex items-center gap-3">
            <Link href="/console" className="rounded text-[13px] text-b-brand underline-offset-2 hover:underline">{b.consoleLink}</Link>
            {step === "feed" && (
              <button onClick={() => setStep("signin")} className="inline-flex items-center gap-1.5 rounded text-[13px] text-b-text-2 hover:text-b-text">
                <LogOut aria-hidden className="size-4" /> {b.signOut}
              </button>
            )}
          </div>
        </div>
      </header>

      <main className="mx-auto max-w-[1100px] px-4 py-8">
        {step === "signin" && (
          <form noValidate onSubmit={signIn} className="mx-auto max-w-[380px] space-y-4 rounded-lg border border-b-border bg-b-surface p-6">
            <h1 className="text-[20px] font-bold">{b.signIn}</h1>
            <Input id="username" name="username" label={b.username} autoComplete="off" error={errors.username} />
            <Input id="board-password" name="password" type="password" label={b.password} autoComplete="off" error={errors.password} />
            <BrandButton type="submit" className="w-full">{b.signInCta}</BrandButton>
          </form>
        )}

        {step === "otp" && (
          <form noValidate onSubmit={verify} className="mx-auto max-w-[380px] space-y-4 rounded-lg border border-b-border bg-b-surface p-6">
            <h1 className="text-[20px] font-bold">{b.otpTitle}</h1>
            <p className="text-[14px] text-b-text-2">{b.otpBody}</p>
            <Input id="otp" name="otp" label={b.otpLabel} inputMode="numeric" autoComplete="one-time-code" maxLength={6} error={errors.otp} autoFocus />
            <BrandButton type="submit" className="w-full">{b.otpCta}</BrandButton>
          </form>
        )}

        {step === "feed" && (
          <>
            <div className="mb-4">
              <h1 className="text-[22px] font-bold">{b.feedTitle}</h1>
              <p className="text-[14px] text-b-text-2">{b.feedNote}</p>
            </div>
            <div className="overflow-x-auto rounded-lg border border-b-border bg-b-surface" tabIndex={0} role="region" aria-label={b.feedTitle}>
              <table className="w-full min-w-[720px] text-left text-[14px]">
                <caption className="sr-only">{b.feedTitle}</caption>
                <thead className="bg-b-bg text-[12.5px] text-b-text-2">
                  <tr>
                    {Object.entries(b.columns).map(([k, v]) => (
                      <th key={k} scope="col" className={`px-4 py-2.5 font-semibold ${["weight", "rate"].includes(k) ? "text-right" : ""}`}>
                        {v || <span className="sr-only">{b.actionColumn}</span>}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {loads.map((l) => {
                    const s = status[l.id];
                    return (
                      <tr key={l.id} className="border-t border-b-border">
                        <td className="whitespace-nowrap px-4 py-2.5 font-mono text-[13px]">{l.id}</td>
                        <td className="whitespace-nowrap px-4 py-2.5">{l.lane}</td>
                        <td className="px-4 py-2.5">{l.equipment}</td>
                        <td className="whitespace-nowrap px-4 py-2.5 text-right tabular">{fill(b.weightLb, { n: l.weight_lb.toLocaleString("en-US") })}</td>
                        <td className="px-4 py-2.5 text-right font-semibold tabular">{fmtUsd(l.rate_usd)}</td>
                        <td className="whitespace-nowrap px-4 py-2.5 text-b-text-2">{fmtAgo(l.posted_at)}</td>
                        <td className="px-4 py-2.5 text-right">
                          {s === "booked" ? (
                            <span id={`status-${l.id}`} tabIndex={-1} className="inline-flex items-center gap-1 text-[13px] font-semibold text-b-ok"><CircleCheck aria-hidden className="size-4" /> {b.booked}</span>
                          ) : s === "taken" ? (
                            <span id={`status-${l.id}`} tabIndex={-1} className="inline-flex items-center gap-1 text-[13px] font-semibold text-b-bad"><CircleX aria-hidden className="size-4" /> {b.taken}</span>
                          ) : (
                            <BrandButton className="h-8 px-3 text-[13px]" onClick={() => setBooking({ load: l, stage: "confirm" })} aria-label={`${b.book} ${l.id}`}>
                              {b.book}
                            </BrandButton>
                          )}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </>
        )}

        <p className="mt-6 flex items-start gap-2 text-[12.5px] text-b-text-2">
          <Info aria-hidden className="mt-px size-4 shrink-0" /> {b.tagline}
        </p>
      </main>

      {booking && (
        <Dialog labelledBy="booking-title" onClose={close} stage={booking.stage} fallbackFocus={focusRowStatus}>
          {booking.stage === "confirm" && (
            <>
              <h2 id="booking-title" className="text-[18px] font-bold">{fill(b.confirmTitle, { id: booking.load.id })}</h2>
              <p className="mt-2 text-[14px] text-b-text-2">{b.confirmBody}</p>
              <p className="mt-3 text-[14px]">{booking.load.lane} · <strong>{fmtUsd(booking.load.rate_usd)}</strong></p>
              <div className="mt-5 flex justify-end gap-2">
                <button onClick={close} className="h-10 rounded border border-b-input-border px-4 text-[14px]">{b.cancel}</button>
                <BrandButton onClick={() => setBooking({ load: booking.load, stage: "captcha" })}>{b.confirmCta}</BrandButton>
              </div>
            </>
          )}
          {booking.stage === "captcha" && (
            <>
              <h2 id="booking-title" className="text-[18px] font-bold">{b.captchaTitle}</h2>
              <p className="mt-2 rounded bg-b-warn-bg px-3 py-2 text-[13px] text-b-text">{b.captchaBody}</p>
              <label className="mt-4 flex cursor-pointer items-center gap-3 rounded border border-b-input-border px-3 py-3 text-[14px]">
                <input type="checkbox" checked={human} onChange={(e) => setHuman(e.target.checked)} className="size-5 accent-[var(--b-brand)]" />
                {b.captchaLabel}
              </label>
              <div className="mt-5 flex justify-end gap-2">
                <button onClick={close} className="h-10 rounded border border-b-input-border px-4 text-[14px]">{b.cancel}</button>
                <BrandButton disabled={!human} onClick={finish}>{b.captchaCta}</BrandButton>
              </div>
            </>
          )}
          {(booking.stage === "success" || booking.stage === "taken") && (
            <div role="status">
              {booking.stage === "success" ? (
                <CircleCheck aria-hidden className="size-8 text-b-ok" />
              ) : (
                <CircleX aria-hidden className="size-8 text-b-bad" />
              )}
              <h2 id="booking-title" className="mt-3 text-[18px] font-bold">{booking.stage === "success" ? b.successTitle : b.takenTitle}</h2>
              <p className="mt-2 text-[14px] text-b-text-2">{booking.stage === "success" ? fill(b.successBody, { ref }) : b.takenBody}</p>
              <div className="mt-5 flex justify-end">
                <BrandButton onClick={close}>{b.backToFeed}</BrandButton>
              </div>
            </div>
          )}
        </Dialog>
      )}
    </div>
  );
}
