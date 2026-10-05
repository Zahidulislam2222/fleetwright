"use client";

import { useEffect, useRef, useState } from "react";
import { paginate } from "@/mocks/data";
import copy from "@/content/console.json";
import { fill } from "@/lib/fill";
import { Button } from "./ui";

export type Column<T> = {
  key: string;
  header: string;
  cell: (row: T) => React.ReactNode;
  align?: "left" | "right";
  className?: string;
};

/**
 * Cursor-paginated table, mirroring the API shape (items + next_cursor). The scroll container is
 * focusable so keyboard users can pan wide tables on narrow screens.
 */
export function DataTable<T>({
  label,
  tenant,
  rows,
  columns,
  rowKey,
  resetKey,
}: {
  label: string;
  tenant: string;
  rows: T[];
  columns: Column<T>[];
  rowKey: (row: T) => string;
  /** Paging resets only when this changes (tenant, filters, search) — not when a row is edited. */
  resetKey: string;
}) {
  const [paging, setPaging] = useState<{ key: string; pages: string[] }>({ key: resetKey, pages: [] });
  // Adjust state while rendering when the key changes, so returning to an earlier key starts fresh.
  if (paging.key !== resetKey) setPaging({ key: resetKey, pages: [] });
  const pages = paging.key === resetKey ? paging.pages : [];

  const regionRef = useRef<HTMLDivElement>(null);
  const bodyRef = useRef<HTMLTableSectionElement>(null);
  /** Row index to focus after "Load more" renders (the button may be gone on the last page). */
  const pendingFocus = useRef<number | null>(null);
  /** The row that currently holds focus, so focus can be rescued if an action removes that row. */
  const focused = useRef<{ key: string; index: number } | null>(null);

  useEffect(() => {
    const body = bodyRef.current;
    if (!body) return;
    const trs = [...body.querySelectorAll<HTMLTableRowElement>("tr[data-row]")];
    if (pendingFocus.current !== null) {
      trs[pendingFocus.current]?.focus();
      pendingFocus.current = null;
      return;
    }
    const f = focused.current;
    const lost = !document.activeElement || document.activeElement === document.body;
    if (f && lost && !trs.some((tr) => tr.dataset.row === f.key)) {
      // e.g. "Drain" under a "Healthy" filter: the row leaves the result set with focus inside it.
      (trs[Math.min(f.index, trs.length - 1)] ?? regionRef.current)?.focus();
      focused.current = null;
    }
  });

  const first = paginate(tenant, rows, null);
  const loaded = [first, ...pages.map((c) => paginate(tenant, rows, c))];
  const visible = loaded.flatMap((p) => p.items);
  const next = loaded[loaded.length - 1].next_cursor;

  return (
    <div className="overflow-hidden rounded-2xl border border-c-border bg-c-surface shadow-[var(--c-shadow)]">
      <div ref={regionRef} className="overflow-x-auto" tabIndex={0} role="region" aria-label={label}>
        <table className="w-full min-w-[720px] border-collapse text-left text-[13.5px]">
          <caption className="sr-only">{label}</caption>
          <thead>
            <tr className="border-b border-c-border bg-c-surface-2">
              {columns.map((c) => (
                <th key={c.key} scope="col" className={`whitespace-nowrap px-4 py-2.5 text-[12px] font-medium text-c-text-3 ${c.align === "right" ? "text-right" : ""}`}>
                  {c.header}
                </th>
              ))}
            </tr>
          </thead>
          <tbody
            ref={bodyRef}
            onFocus={(e) => {
              const tr = (e.target as HTMLElement).closest<HTMLTableRowElement>("tr[data-row]");
              if (tr) focused.current = { key: tr.dataset.row ?? "", index: tr.sectionRowIndex };
            }}
            onBlur={(e) => {
              if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget as Node)) focused.current = null;
            }}
          >
            {visible.map((row) => (
              <tr key={rowKey(row)} data-row={rowKey(row)} tabIndex={-1} className="border-b border-c-border outline-none last:border-b-0 hover:bg-c-surface-2 focus-visible:bg-c-surface-2">
                {columns.map((c) => (
                  <td key={c.key} className={`whitespace-nowrap px-4 py-2.5 align-middle text-c-text ${c.align === "right" ? "text-right tabular" : ""} ${c.className ?? ""}`}>
                    {c.cell(row)}
                  </td>
                ))}
              </tr>
            ))}
            {visible.length === 0 && (
              <tr>
                <td colSpan={columns.length} className="px-4 py-10 text-center text-c-text-2">{copy.common.noMatches}</td>
              </tr>
            )}
          </tbody>
        </table>
      </div>
      <div className="flex flex-wrap items-center justify-between gap-3 border-t border-c-border px-4 py-2.5">
        <p className="text-[12.5px] text-c-text-3 tabular" aria-live="polite">
          {fill(copy.common.showing, { shown: visible.length, total: first.total_estimate })}
          {next && <span className="ml-2 font-mono text-[11px]">{fill(copy.common.nextCursor, { cursor: next })}</span>}
        </p>
        {next && (
          <Button
            onClick={() => {
              pendingFocus.current = visible.length;
              setPaging({ key: resetKey, pages: [...pages, next] });
            }}
          >{copy.common.loadMore}</Button>
        )}
      </div>
    </div>
  );
}
