"use client";

import { useSyncExternalStore } from "react";
import type { Session } from "@/mocks/types";
import config from "@/config/live.json";
import { setRealClock } from "@/mocks/data";
import { ApiError, apiGet, setCsrfFrom } from "./api";

/**
 * Whether the console talks to a real backend, and who is looking.
 *
 * - `checking`: asking `/v1/session` (first paint renders the prototype skeleton state).
 * - `live`: the API answered. `session` is null when sign-in is required (public reading is off).
 * - `prototype`: no API behind this site (the static preview): every screen uses the mock data.
 *
 * `tick` advances whenever the server says something changed (live-update stream) or, while the
 * stream is down, on a polling timer; data hooks refetch when it moves.
 */
export type Mode = "checking" | "live" | "prototype";
type Snapshot = { mode: Mode; session: Session | null; tick: number; streaming: boolean };

const SERVER: Snapshot = { mode: "checking", session: null, tick: 0, streaming: false };
let current: Snapshot = SERVER;
let started = false;
let stream: EventSource | null = null;
let poll: ReturnType<typeof setInterval> | null = null;
let pending: ReturnType<typeof setTimeout> | null = null;
const listeners = new Set<() => void>();

function set(patch: Partial<Snapshot>) {
  current = { ...current, ...patch };
  listeners.forEach((l) => l());
}

function bump() {
  if (pending) return;
  pending = setTimeout(() => {
    pending = null;
    set({ tick: current.tick + 1 });
  }, config.eventThrottleMs);
}

function startPolling() {
  if (!poll) poll = setInterval(() => set({ tick: current.tick + 1 }), config.pollMs);
}

function stopPolling() {
  if (poll) clearInterval(poll);
  poll = null;
}

function connect() {
  stream?.close();
  stream = null;
  if (current.mode !== "live" || typeof EventSource === "undefined") return;
  startPolling(); // until the stream proves it is open
  const es = new EventSource("/v1/stream");
  stream = es;
  es.addEventListener("hello", () => {
    stopPolling();
    set({ streaming: true });
  });
  es.addEventListener("update", bump);
  es.onerror = () => {
    // EventSource reconnects by itself; poll meanwhile so the screen never goes stale.
    set({ streaming: false });
    startPolling();
  };
}

/** Asks the API who we are. Called on start, after sign-in/out, and when a request gets a 401. */
export async function refreshSession(): Promise<void> {
  try {
    const session = await apiGet<Session>("/v1/session");
    setCsrfFrom(session);
    setRealClock(true);
    const reconnect = current.mode !== "live" || current.session?.role !== session.role || current.session?.tenant.id !== session.tenant.id;
    set({ mode: "live", session });
    if (reconnect) connect();
  } catch (err) {
    setCsrfFrom(null);
    if (err instanceof ApiError && err.status === 401) {
      setRealClock(true);
      set({ mode: "live", session: null, streaming: false });
      stream?.close();
      stream = null;
      stopPolling();
    } else if (current.mode === "checking") {
      set({ mode: "prototype" });
    }
    // A live console that loses the API keeps its mode; data hooks show their error state.
  }
}

function subscribe(listener: () => void) {
  listeners.add(listener);
  if (!started && typeof window !== "undefined") {
    started = true;
    void refreshSession();
  }
  return () => listeners.delete(listener);
}

export function useLive(): Snapshot {
  return useSyncExternalStore(
    subscribe,
    () => current,
    () => SERVER,
  );
}
