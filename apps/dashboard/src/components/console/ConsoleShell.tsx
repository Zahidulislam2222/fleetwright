"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useCallback, useEffect, useRef, useState } from "react";
import { useDialog } from "@/lib/useDialog";
import { RadioGroup } from "./RadioGroup";
import { CircleDashed, LogIn, LogOut, Menu, Monitor, Moon, Sun, X } from "lucide-react";
import { FleetMark } from "@/components/brand/FleetMark";
import { fmtDateTime, tenants } from "@/mocks/data";
import seed from "@/mocks/seed.json";
import copy from "@/content/console.json";
import { navIcons } from "./icons";
import { usePrototype, type DataStateKind, type ThemeChoice } from "./prototypeStore";
import { refreshSession, useLive } from "@/lib/live/store";
import { apiSend } from "@/lib/live/api";
import config from "@/config/live.json";
import { fill } from "@/lib/fill";

const L = copy.live;

/** Where the data comes from, said plainly in the header. */
function SourceBanner() {
  const { mode, session, streaming } = useLive();
  const pill = "hidden min-w-0 truncate rounded-full border border-c-border bg-c-surface px-3 py-1 font-mono text-[11.5px] text-c-text-2 sm:block";
  if (mode === "checking") return <p className={pill}>{L.checking}</p>;
  if (mode === "prototype")
    return (
      <p className={pill}>
        <span className="mr-1.5 inline-block size-1.5 -translate-y-px rounded-full bg-c-accent align-middle" aria-hidden />
        {copy.mockBanner} {fmtDateTime(seed.asOf)}
      </p>
    );
  return (
    <p className={pill}>
      <span className={`mr-1.5 inline-block size-1.5 -translate-y-px rounded-full align-middle ${streaming ? "bg-c-ok" : "bg-c-warn"}`} aria-hidden />
      {L.banner} · {session?.tenant.name} · {streaming ? L.streaming : fill(L.polling, { s: Math.round(config.pollMs / 1000) })}
    </p>
  );
}

function Account() {
  const { mode, session } = useLive();
  const [busy, setBusy] = useState(false);
  if (mode !== "live") return null;
  if (!session?.authenticated)
    return (
      <Link href="/login" className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-c-border bg-c-surface px-3 text-[13px] text-c-text hover:bg-c-surface-2">
        <LogIn aria-hidden className="size-4" />
        <span className="hidden sm:inline">{session ? L.publicView : L.signIn}</span>
        <span className="sm:hidden">{L.signIn}</span>
      </Link>
    );
  return (
    <div className="flex items-center gap-2">
      <span className="hidden text-[12.5px] text-c-text-2 md:inline">{fill(L.signedInAs, { name: session.name ?? "", role: L.roles[session.role] })}</span>
      <button
        type="button"
        disabled={busy}
        onClick={() => {
          setBusy(true);
          apiSend("POST", "/v1/auth/logout")
            .catch(() => undefined)
            .finally(() => {
              setBusy(false);
              void refreshSession();
            });
        }}
        className="inline-flex h-9 items-center gap-1.5 rounded-lg border border-c-border bg-c-surface px-3 text-[13px] text-c-text hover:bg-c-surface-2 disabled:opacity-50"
      >
        <LogOut aria-hidden className="size-4" />
        <span className="hidden sm:inline">{L.signOut}</span>
        <span className="sr-only sm:hidden">{L.signOut}</span>
      </button>
    </div>
  );
}

const STATES = Object.keys(copy.states) as DataStateKind[];
const THEMES: { id: ThemeChoice; icon: typeof Sun }[] = [
  { id: "system", icon: Monitor },
  { id: "light", icon: Sun },
  { id: "dark", icon: Moon },
];

function isActive(pathname: string, href: string) {
  return href === "/console" ? pathname === href : pathname === href || pathname.startsWith(`${href}/`);
}

function NavList({ pathname, onNavigate }: { pathname: string; onNavigate?: () => void }) {
  return (
    <nav aria-label={copy.shell.navLabel} className="flex flex-1 flex-col gap-6">
      <ul className="space-y-0.5">
        {copy.nav.map((item) => {
          const Icon = navIcons[item.icon] ?? CircleDashed;
          const active = isActive(pathname, item.href);
          return (
            <li key={item.href}>
              <Link
                href={item.href}
                onClick={onNavigate}
                aria-current={active ? "page" : undefined}
                className={`flex items-center gap-3 rounded-lg px-3 py-2 text-[14px] transition-colors duration-150 ${
                  active ? "bg-c-surface-3 font-medium text-c-text" : "text-c-text-2 hover:bg-c-surface-2 hover:text-c-text"
                }`}
              >
                <Icon aria-hidden className={`size-4 ${active ? "text-c-accent-text" : ""}`} />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
      <ul className="mt-auto space-y-0.5 border-t border-c-border pt-4">
        {copy.navSecondary.map((item) => {
          const Icon = navIcons[item.icon] ?? CircleDashed;
          return (
            <li key={item.href}>
              <Link href={item.href} onClick={onNavigate} className="flex items-center gap-3 rounded-lg px-3 py-2 text-[14px] text-c-text-2 transition-colors hover:bg-c-surface-2 hover:text-c-text">
                <Icon aria-hidden className="size-4" />
                {item.label}
              </Link>
            </li>
          );
        })}
      </ul>
    </nav>
  );
}

function Brand() {
  return (
    <Link href="/console" className="flex items-center gap-2.5 rounded-lg px-1">
      <span className="grid size-8 place-items-center rounded-full bg-c-text text-c-bg">
        <FleetMark className="size-4" />
      </span>
      <span className="font-pixel text-[18px] text-c-text">{copy.product}</span>
    </Link>
  );
}

function MobileDrawer({ pathname, onClose }: { pathname: string; onClose: () => void }) {
  const rootRef = useRef<HTMLDivElement>(null);
  const ref = useRef<HTMLDivElement>(null);
  const focusMain = useCallback(() => document.getElementById("console-main"), []);
  useDialog(ref, onClose, undefined, focusMain);

  // Lock page scroll while open. Close when the drawer's own `lg:hidden` hides it (viewport widened),
  // reading the rendered state rather than repeating the breakpoint value here.
  useEffect(() => {
    document.body.style.overflow = "hidden";
    const onResize = () => {
      if (rootRef.current && getComputedStyle(rootRef.current).display === "none") onClose();
    };
    window.addEventListener("resize", onResize);
    return () => {
      document.body.style.overflow = "";
      window.removeEventListener("resize", onResize);
    };
  }, [onClose]);

  return (
    <div ref={rootRef} className="fixed inset-0 z-[var(--z-overlay)] lg:hidden">
      <button aria-label={copy.shell.closeMenu} tabIndex={-1} className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div ref={ref} role="dialog" aria-modal="true" aria-label={copy.shell.drawerLabel} className="absolute inset-y-0 left-0 flex w-[min(300px,86vw)] flex-col gap-6 border-r border-c-border bg-c-surface px-3 py-4 shadow-2xl">
        <div className="flex items-center justify-between">
          <Brand />
          <button onClick={onClose} aria-label={copy.shell.closeMenu} className="grid size-10 place-items-center rounded-lg text-c-text-2 hover:bg-c-surface-2">
            <X aria-hidden className="size-5" />
          </button>
        </div>
        <NavList pathname={pathname} onNavigate={onClose} />
      </div>
    </div>
  );
}

export function ConsoleShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const proto = usePrototype();
  const { mode } = useLive();
  const live = mode === "live";
  const [open, setOpen] = useState(false);
  const closeDrawer = useCallback(() => setOpen(false), []);

  return (
    <div className="console-theme min-h-svh bg-c-bg text-c-text">
      <a href="#console-main" className="skip-link">{copy.shell.skipLink}</a>

      {/* Desktop sidebar */}
      <aside className="fixed inset-y-0 left-0 z-[var(--z-sticky)] hidden w-[248px] flex-col gap-6 border-r border-c-border bg-c-surface px-3 py-4 lg:flex">
        <Brand />
        <NavList pathname={pathname} />
      </aside>

      {/* Mobile drawer */}
      {open && <MobileDrawer pathname={pathname} onClose={closeDrawer} />}

      <div className="lg:pl-[248px]">
        <header className="sticky top-0 z-[var(--z-sticky)] border-b border-c-border bg-c-bg/90 backdrop-blur-md">
          <div className="flex h-14 items-center gap-3 px-4 lg:px-8">
            <button onClick={() => setOpen(true)} aria-label={copy.shell.openMenu} aria-expanded={open} className="grid size-10 place-items-center rounded-lg text-c-text-2 hover:bg-c-surface-2 lg:hidden">
              <Menu aria-hidden className="size-5" />
            </button>
            <SourceBanner />
            <div className="ml-auto flex items-center gap-2">
              {!live && (
              <>
              <label className="sr-only" htmlFor="tenant-select">{copy.shell.tenantLabel}</label>
              <select
                id="tenant-select"
                value={proto.tenant}
                onChange={(e) => proto.setTenant(e.target.value)}
                className="h-9 rounded-lg border border-c-input-border bg-c-surface px-2.5 text-[13.5px] text-c-text"
              >
                {tenants.map((t) => (
                  <option key={t.id} value={t.id}>{t.name}</option>
                ))}
              </select>
              </>
              )}
              <Account />
              <RadioGroup
                label={copy.shell.themeLabel}
                value={proto.theme}
                onChange={proto.setTheme}
                className="flex rounded-lg border border-c-border bg-c-surface p-0.5"
                options={THEMES.map(({ id, icon: Icon }) => ({ value: id, label: copy.shell.themes[id], content: <Icon aria-hidden className="size-4" /> }))}
                optionClass={(on) => `grid size-8 place-items-center rounded-md transition-colors ${on ? "bg-c-surface-3 text-c-text" : "text-c-text-3 hover:text-c-text"}`}
              />
            </div>
          </div>
          {!live && (
          <div className="flex flex-wrap items-center gap-x-3 gap-y-1.5 border-t border-c-border px-4 py-2 lg:px-8">
            <span id="state-label" className="shrink-0 font-mono text-[11px] uppercase tracking-[0.14em] text-c-text-3">{copy.shell.stateLabel}</span>
            <RadioGroup
              labelledBy="state-label"
              value={proto.state}
              onChange={proto.setState}
              className="flex flex-wrap gap-1"
              options={STATES.map((st) => ({ value: st, label: copy.states[st] }))}
              optionClass={(on) => `rounded-full px-3 py-1 text-[12.5px] transition-colors ${on ? "bg-c-text text-c-bg" : "border border-c-border text-c-text-2 hover:text-c-text"}`}
            />
          </div>
          )}
        </header>
        <main id="console-main" tabIndex={-1} className="mx-auto max-w-[1360px] px-4 py-6 outline-none lg:px-8 lg:py-8">
          {children}
        </main>
      </div>
    </div>
  );
}
