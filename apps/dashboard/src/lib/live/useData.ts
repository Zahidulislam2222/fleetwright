"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import type { Page, Session } from "@/mocks/types";
import config from "@/config/live.json";
import { usePrototype, type DataStateKind } from "@/components/console/prototypeStore";
import { ApiError, apiGet } from "./api";
import { refreshSession, useLive, type Mode } from "./store";

/**
 * One interface for both data sources. In `prototype` mode the hooks return mock data and the
 * state chosen in the preview switcher; in `live` mode they fetch from the API and refetch when the
 * live-update stream (or the polling fallback) says something changed. Earlier data stays on screen
 * while a refetch runs, so screens never flash back to a skeleton.
 */
export type Source = {
  mode: Mode;
  live: boolean;
  session: Session | null;
  /** The tenant being shown: the session's in live mode, the switcher's in the prototype. */
  tenant: string;
};

export function useSource(): Source {
  const { mode, session } = useLive();
  const proto = usePrototype();
  const live = mode === "live";
  return { mode, live, session, tenant: live ? (session?.tenant.id ?? "") : proto.tenant };
}

type Fetched<T> = { status: DataStateKind; data: T | null; error: string | null };

function statusOf(err: unknown): DataStateKind {
  return err instanceof ApiError && (err.status === 401 || err.status === 403) ? "denied" : "error";
}

/** GET `path` while live (null = don't fetch). Refetches on every tick; keeps the last good data. */
export function useLiveGet<T>(path: string | null): Fetched<T> & { reload: () => void } {
  const { tick, mode } = useLive();
  const [state, setState] = useState<Fetched<T> & { path: string | null }>({ status: "loading", data: null, error: null, path });
  const [nonce, setNonce] = useState(0);
  // A different path is a different resource: start from loading, not from the old data.
  if (state.path !== path) setState({ status: "loading", data: null, error: null, path });

  useEffect(() => {
    if (!path || mode !== "live") return;
    const ctrl = new AbortController();
    apiGet<T>(path, ctrl.signal)
      .then((data) => setState({ status: "ready", data, error: null, path }))
      .catch((err: unknown) => {
        if (ctrl.signal.aborted) return;
        if (err instanceof ApiError && err.status === 401) void refreshSession();
        setState((s) => (s.data && statusOf(err) === "error" ? s : { status: statusOf(err), data: null, error: String((err as Error).message), path }));
      });
    return () => ctrl.abort();
  }, [path, mode, tick, nonce]);

  const reload = useCallback(() => setNonce((n) => n + 1), []);
  return { status: state.status, data: state.data, error: state.error, reload };
}

export type ListResult<T> = {
  source: Source;
  status: DataStateKind;
  rows: T[];
  retry: () => void;
  /** Live cursor paging: older rows exist on the server. */
  hasMore: boolean;
  loadingMore: boolean;
  more: () => void;
};

/**
 * A tenant list. Live: the newest `listLimit` rows, refreshed on every tick, with older pages
 * fetched on demand through `next_cursor` (kept across refreshes, de-duplicated by id).
 */
export function useList<T extends { id: string }>(resource: string, mock: (tenant: string) => T[], query = ""): ListResult<T> {
  const source = useSource();
  const proto = usePrototype();
  const sep = query ? "&" : "?";
  const base = `/v1/${resource}${query ? `?${query}` : ""}`;
  const first = useLiveGet<Page<T>>(source.live && source.session ? `${base}${sep}limit=${config.listLimit}` : null);
  const [older, setOlder] = useState<{ base: string; rows: T[]; cursor: string | null | undefined }>({ base, rows: [], cursor: undefined });
  const [loadingMore, setLoadingMore] = useState(false);
  const busy = useRef(false);
  if (older.base !== base) setOlder({ base, rows: [], cursor: undefined });

  const firstItems = first.data?.items ?? [];
  const cursor = older.cursor === undefined ? (first.data?.next_cursor ?? null) : older.cursor;

  const more = useCallback(() => {
    if (!cursor || busy.current) return;
    busy.current = true;
    setLoadingMore(true);
    apiGet<Page<T>>(`${base}${sep}limit=${config.listLimit}&cursor=${encodeURIComponent(cursor)}`)
      .then((page) => setOlder((o) => ({ base: o.base, rows: [...o.rows, ...page.items], cursor: page.next_cursor })))
      .catch(() => undefined)
      .finally(() => {
        busy.current = false;
        setLoadingMore(false);
      });
  }, [base, cursor, sep]);

  if (!source.live) {
    return {
      source,
      status: source.mode === "checking" ? "loading" : proto.state,
      rows: source.mode === "checking" ? [] : mock(source.tenant),
      retry: () => proto.setState("ready"),
      hasMore: false,
      loadingMore: false,
      more: () => undefined,
    };
  }
  const seen = new Set(firstItems.map((r) => r.id));
  const rows = [...firstItems, ...older.rows.filter((r) => !seen.has(r.id))];
  const status = !source.session ? "denied" : first.status === "ready" && rows.length === 0 ? "empty" : first.status;
  return { source, status, rows, retry: first.reload, hasMore: Boolean(cursor), loadingMore, more };
}

/** A single live object (overview, latency, demo status), or the mock equivalent. */
export function useObject<T>(path: string, mock: (tenant: string) => T): { source: Source; status: DataStateKind; data: T | null; retry: () => void } {
  const source = useSource();
  const proto = usePrototype();
  const got = useLiveGet<T>(source.live && source.session ? path : null);
  if (!source.live) {
    const ready = source.mode !== "checking";
    return { source, status: ready ? proto.state : "loading", data: ready ? mock(source.tenant) : null, retry: () => proto.setState("ready") };
  }
  return { source, status: source.session ? got.status : "denied", data: got.data, retry: got.reload };
}
