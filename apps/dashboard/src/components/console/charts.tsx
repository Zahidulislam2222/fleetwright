"use client";

import { useEffect, useRef, useState } from "react";
import copy from "@/content/console.json";
import { fill } from "@/lib/fill";

/*
 * Chart colours come from --c-series-* / --c-ord-* tokens, validated with the dataviz palette checker
 * against both console surfaces. Text always uses text tokens; colour only marks identity.
 */

function useWidth<T extends HTMLElement>() {
  const ref = useRef<T>(null);
  const [width, setWidth] = useState(0);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setWidth(Math.floor(e.contentRect.width)));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, width] as const;
}

function niceMax(v: number) {
  if (v <= 0) return 1;
  const pow = 10 ** Math.floor(Math.log10(v));
  const n = v / pow;
  const step = n <= 1 ? 1 : n <= 2 ? 2 : n <= 2.5 ? 2.5 : n <= 5 ? 5 : 10;
  return step * pow;
}

function Tooltip({ x, y, width, children }: { x: number; y: number; width: number; children: React.ReactNode }) {
  const w = 168;
  const left = Math.min(Math.max(8, x + 14), Math.max(8, width - w - 8));
  return (
    <div
      role="presentation"
      className="pointer-events-none absolute z-10 rounded-lg border border-c-border bg-c-surface px-3 py-2 text-[12.5px] shadow-[var(--c-shadow)]"
      style={{ left, top: Math.max(4, y - 10), width: w }}
    >
      {children}
    </div>
  );
}

/* ─── Line chart: one axis, crosshair + tooltip, legend + direct end labels ── */

export type LineSeries = { id: string; label: string; color: string; points: number[] };

export function LineChart({ title, xLabels, series, height = 240, valueSuffix = "" }: { title: string; xLabels: string[]; series: LineSeries[]; height?: number; valueSuffix?: string }) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  const pad = { l: 36, r: 88, t: 12, b: 26 };
  const n = xLabels.length;
  const max = niceMax(Math.max(...series.flatMap((s) => s.points)));
  const iw = Math.max(0, width - pad.l - pad.r);
  const ih = height - pad.t - pad.b;
  const x = (i: number) => pad.l + (n <= 1 ? 0 : (i / (n - 1)) * iw);
  const y = (v: number) => pad.t + ih - (v / max) * ih;
  const ticks = [0, max / 2, max];

  const onMove = (e: React.PointerEvent<SVGSVGElement>) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = e.clientX - r.left - pad.l;
    setHover(Math.min(n - 1, Math.max(0, Math.round((px / iw) * (n - 1)))));
  };
  const onKey = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowRight") setHover((h) => Math.min(n - 1, (h ?? -1) + 1));
    else if (e.key === "ArrowLeft") setHover((h) => Math.max(0, (h ?? n) - 1));
    else if (e.key === "Escape") setHover(null);
    else return;
    e.preventDefault();
  };

  return (
    <figure className="m-0">
      <figcaption className="sr-only">{title}</figcaption>
      {series.length > 1 && (
        <ul className="mb-3 flex flex-wrap gap-4 text-[12.5px] text-c-text-2">
          {series.map((s) => (
            <li key={s.id} className="flex items-center gap-2">
              <span aria-hidden className="h-0.5 w-4 rounded-full" style={{ background: s.color }} />
              {s.label}
            </li>
          ))}
        </ul>
      )}
      <div ref={ref} className="relative">
        {width > 0 && (
          <svg
            width={width}
            height={height}
            role="img"
            aria-label={fill(copy.charts.lineKeys, { title })}
            tabIndex={0}
            onPointerMove={onMove}
            onPointerLeave={() => setHover(null)}
            onKeyDown={onKey}
            onBlur={() => setHover(null)}
            className="block touch-pan-y rounded-md"
          >
            {ticks.map((t) => (
              <g key={t}>
                <line x1={pad.l} x2={pad.l + iw} y1={y(t)} y2={y(t)} stroke={t === 0 ? "var(--c-border-strong)" : "var(--c-grid)"} strokeWidth={1} />
                <text x={pad.l - 8} y={y(t)} dy="0.32em" textAnchor="end" className="fill-c-text-3 text-[11px] tabular">{Math.round(t)}</text>
              </g>
            ))}
            {xLabels.map((l, i) =>
              i % 3 === 2 || i === n - 1 ? (
                <text key={l} x={x(i)} y={height - 6} textAnchor="middle" className="fill-c-text-3 text-[11px] tabular">{l}</text>
              ) : null,
            )}
            {hover !== null && <line x1={x(hover)} x2={x(hover)} y1={pad.t} y2={pad.t + ih} stroke="var(--c-border-strong)" strokeWidth={1} />}
            {series.map((s) => (
              <g key={s.id}>
                <path
                  d={s.points.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join("")}
                  fill="none"
                  stroke={s.color}
                  strokeWidth={2}
                  strokeLinejoin="round"
                  strokeLinecap="round"
                />
                <circle cx={x(n - 1)} cy={y(s.points[n - 1])} r={4} fill={s.color} stroke="var(--c-surface)" strokeWidth={2} />
                <text x={x(n - 1) + 10} y={y(s.points[n - 1])} dy="0.32em" className="fill-c-text-2 text-[12px]">
                  {s.label} {s.points[n - 1]}
                </text>
                {hover !== null && <circle cx={x(hover)} cy={y(s.points[hover])} r={4} fill={s.color} stroke="var(--c-surface)" strokeWidth={2} />}
              </g>
            ))}
          </svg>
        )}
        {hover !== null && width > 0 && (
          <Tooltip x={x(hover)} y={pad.t} width={width}>
            <p className="mb-1 text-c-text-3 tabular">{xLabels[hover]}</p>
            {series.map((s) => (
              <p key={s.id} className="flex items-center gap-2">
                <span aria-hidden className="h-0.5 w-3 rounded-full" style={{ background: s.color }} />
                <strong className="font-semibold text-c-text tabular">{s.points[hover]}{valueSuffix}</strong>
                <span className="text-c-text-2">{s.label}</span>
              </p>
            ))}
          </Tooltip>
        )}
        <p aria-live="polite" className="sr-only">
          {hover !== null ? `${xLabels[hover]}: ${series.map((s) => `${s.label} ${s.points[hover]}`).join(", ")}` : ""}
        </p>
      </div>
    </figure>
  );
}

/* ─── Horizontal grouped bars (ordinal ramp), per-bar hover/focus ── */

export type BarGroup = { id: string; label: string; values: number[] };

export function GroupedBars({
  title,
  groups,
  keys,
  format,
}: {
  title: string;
  groups: BarGroup[];
  keys: { label: string; color: string }[];
  format: (v: number) => string;
}) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<{ g: number; k: number } | null>(null);
  const labelW = width < 520 ? 0 : 150;
  const bar = 10;
  const gap = 2;
  const groupH = keys.length * (bar + gap) + 22 + (labelW ? 0 : 18);
  const pad = { l: labelW, r: 76, t: 4, b: 24 };
  const height = pad.t + groups.length * groupH + pad.b;
  const max = niceMax(Math.max(...groups.flatMap((g) => g.values)));
  const iw = Math.max(0, width - pad.l - pad.r);
  const sx = (v: number) => (v / max) * iw;
  const ticks = [0, max / 4, max / 2, (3 * max) / 4, max];

  return (
    <figure className="m-0">
      <figcaption className="sr-only">{title}</figcaption>
      <ul className="mb-3 flex flex-wrap gap-4 text-[12.5px] text-c-text-2">
        {keys.map((k) => (
          <li key={k.label} className="flex items-center gap-2">
            <span aria-hidden className="size-2.5 rounded-sm" style={{ background: k.color }} />
            {k.label}
          </li>
        ))}
      </ul>
      <div ref={ref} className="relative">
        {width > 0 && (
          <svg width={width} height={height} role="group" aria-label={title} className="block">
            {ticks.map((t) => (
              <g key={t}>
                <line x1={pad.l + sx(t)} x2={pad.l + sx(t)} y1={pad.t} y2={height - pad.b} stroke={t === 0 ? "var(--c-border-strong)" : "var(--c-grid)"} strokeWidth={1} />
                <text x={pad.l + sx(t)} y={height - 6} textAnchor={t === 0 ? "start" : "middle"} className="fill-c-text-3 text-[11px] tabular">{format(Math.round(t))}</text>
              </g>
            ))}
            {groups.map((g, gi) => {
              const gy = pad.t + gi * groupH + (labelW ? 8 : 22);
              return (
                <g key={g.id}>
                  <text x={labelW ? 0 : pad.l} y={labelW ? gy + ((keys.length * (bar + gap)) / 2) : gy - 8} dy="0.32em" className="fill-c-text text-[12.5px]">{g.label}</text>
                  {g.values.map((v, ki) => {
                    const by = gy + ki * (bar + gap);
                    const w = Math.max(8, sx(v));
                    const active = hover?.g === gi && hover.k === ki;
                    return (
                      <g
                        key={ki}
                        tabIndex={0}
                        role="img"
                        aria-label={`${g.label}, ${keys[ki].label}: ${format(v)}`}
                        onPointerEnter={() => setHover({ g: gi, k: ki })}
                        onPointerLeave={() => setHover(null)}
                        onFocus={() => setHover({ g: gi, k: ki })}
                        onBlur={() => setHover(null)}
                        className="outline-none"
                      >
                        {/* Hit target taller than the mark */}
                        <rect x={pad.l} y={by - 1} width={Math.max(w, iw)} height={bar + gap} fill="transparent" />
                        <path
                          d={`M${pad.l},${by} h${w - 4} a4,4 0 0 1 4,4 v${bar - 8} a4,4 0 0 1 -4,4 h${-(w - 4)} z`}
                          fill={keys[ki].color}
                          opacity={hover && !active ? 0.55 : 1}
                          stroke={active ? "var(--c-text)" : "none"}
                          strokeWidth={active ? 1 : 0}
                        />
                        {ki === keys.length - 1 && (
                          <text x={pad.l + w + 6} y={by + bar / 2} dy="0.32em" className="fill-c-text-2 text-[11.5px] tabular">{format(v)}</text>
                        )}
                      </g>
                    );
                  })}
                </g>
              );
            })}
          </svg>
        )}
        {hover && width > 0 && (
          <Tooltip x={pad.l + sx(groups[hover.g].values[hover.k])} y={pad.t + hover.g * groupH} width={width}>
            <p className="mb-1 text-c-text-3">{groups[hover.g].label}</p>
            <p className="flex items-center gap-2">
              <span aria-hidden className="size-2.5 rounded-sm" style={{ background: keys[hover.k].color }} />
              <strong className="font-semibold text-c-text tabular">{format(groups[hover.g].values[hover.k])}</strong>
              <span className="text-c-text-2">{keys[hover.k].label}</span>
            </p>
          </Tooltip>
        )}
      </div>
    </figure>
  );
}

/* ─── Sparkbars: one series, last bar flagged with status colour + text ── */

export function Sparkbars({ values, label, flagLast }: { values: number[]; label: string; flagLast: boolean }) {
  const max = Math.max(1, ...values);
  const w = 7;
  const gap = 2;
  const h = 28;
  return (
    <svg width={values.length * (w + gap)} height={h} role="img" aria-label={`${label}: ${values.join(", ")}`} className="block">
      {values.map((v, i) => {
        const bh = Math.max(2, (v / max) * h);
        const flagged = flagLast && i === values.length - 1;
        return (
          <rect key={i} x={i * (w + gap)} y={h - bh} width={w} height={bh} rx={2} fill={flagged ? "var(--c-bad)" : "var(--c-series-1)"} opacity={flagged ? 1 : 0.85}>
            <title>{fill(copy.charts.cycle, { i: i + 1, v })}</title>
          </rect>
        );
      })}
    </svg>
  );
}
