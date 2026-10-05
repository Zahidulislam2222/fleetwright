"use client";

import { useSyncExternalStore } from "react";
import seed from "@/mocks/seed.json";
import { PROTOTYPE_STORAGE_KEY } from "@/lib/prototypeKeys";

/**
 * Prototype-only UI state shared by every console screen: which data state to preview, which tenant,
 * which theme. Persisted per tab in sessionStorage (a per-viewer convenience; safe to lose).
 * The server snapshot is the default, so hydration always matches; the stored value applies after.
 */
export type DataStateKind = "ready" | "loading" | "empty" | "error" | "denied";
export type ThemeChoice = "system" | "light" | "dark";

type Snapshot = { state: DataStateKind; tenant: string; theme: ThemeChoice };

const STORAGE_KEY = PROTOTYPE_STORAGE_KEY;
const DEFAULTS: Snapshot = { state: "ready", tenant: seed.tenants[0].id, theme: "system" };

let current: Snapshot = DEFAULTS;
let loaded = false;
const listeners = new Set<() => void>();

/** The theme lives on <html data-console-theme> so the root-layout script can apply it before paint. */
function applyTheme(theme: ThemeChoice) {
  const root = document.documentElement;
  if (theme === "system") delete root.dataset.consoleTheme;
  else root.dataset.consoleTheme = theme;
}

function load() {
  if (loaded || typeof window === "undefined") return;
  loaded = true;
  try {
    const raw = window.sessionStorage.getItem(STORAGE_KEY);
    if (!raw) return;
    const parsed = JSON.parse(raw) as Partial<Snapshot>;
    current = {
      state: (["ready", "loading", "empty", "error", "denied"] as const).includes(parsed.state as DataStateKind) ? (parsed.state as DataStateKind) : DEFAULTS.state,
      tenant: seed.tenants.some((t) => t.id === parsed.tenant) ? (parsed.tenant as string) : DEFAULTS.tenant,
      theme: (["system", "light", "dark"] as const).includes(parsed.theme as ThemeChoice) ? (parsed.theme as ThemeChoice) : DEFAULTS.theme,
    };
    applyTheme(current.theme);
  } catch {
    // Storage blocked (private mode, sandbox): defaults are fine.
  }
}

function set(patch: Partial<Snapshot>) {
  current = { ...current, ...patch };
  if (patch.theme) applyTheme(patch.theme);
  try {
    window.sessionStorage.setItem(STORAGE_KEY, JSON.stringify(current));
  } catch {
    // Not persisted; the in-memory value still applies.
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void) {
  load();
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function usePrototype() {
  const snap = useSyncExternalStore(
    subscribe,
    () => {
      load();
      return current;
    },
    () => DEFAULTS,
  );
  return {
    ...snap,
    setState: (state: DataStateKind) => set({ state }),
    setTenant: (tenant: string) => set({ tenant }),
    setTheme: (theme: ThemeChoice) => set({ theme }),
  };
}
