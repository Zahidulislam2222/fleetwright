"use client";

import { LayoutGroup, motion } from "motion/react";
import { Power, RotateCcw } from "lucide-react";
import { useState } from "react";
import { FleetMark } from "@/components/brand/FleetMark";
import { Reveal } from "./Reveal";
import { easeOutExpo } from "@/design/motion";
import landing from "@/content/landing.json";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";

const TENANTS = landing.cells.tenants;
const WORKERS_PER_CELL = landing.cells.workersPerCell;

function Cell({ index, failed, tenants }: { index: number; failed: boolean; tenants: string[] }) {
  const { cells } = landing;
  const reduced = usePrefersReducedMotion();
  return (
    <motion.div
      layout
      animate={{
        borderColor: failed ? "rgba(255,107,107,0.45)" : "rgba(255,255,255,0.12)",
        backgroundColor: failed ? "rgba(255,107,107,0.05)" : "rgba(255,255,255,0.02)",
      }}
      transition={{ duration: 0.5, ease: easeOutExpo }}
      className="flex flex-col rounded-[24px] border p-5"
    >
      <div className="flex items-center justify-between gap-3">
        <p className="whitespace-nowrap font-pixel text-[22px] text-white">{cells.cellLabels[index]}</p>
        <span
          className={`inline-flex shrink-0 items-center gap-1.5 whitespace-nowrap rounded-full px-2.5 py-1 font-mono text-[11px] ${
            failed ? "bg-[rgba(255,107,107,0.12)] text-[var(--signal-bad)]" : "bg-[rgba(74,222,128,0.12)] text-[var(--signal-ok)]"
          }`}
        >
          <span aria-hidden className={`size-1.5 rounded-full ${failed ? "bg-[var(--signal-bad)]" : "animate-pulse bg-[var(--signal-ok)]"}`} />
          {failed ? cells.statusFailed : cells.statusHealthy}
        </span>
      </div>

      <div aria-hidden className="mt-5 grid grid-cols-6 gap-2">
        {Array.from({ length: WORKERS_PER_CELL }, (_, i) => (
          <motion.span
            key={i}
            animate={{ opacity: failed ? 0.18 : reduced ? 1 : [0.55, 1, 0.55] }}
            transition={failed || reduced ? { duration: 0.4 } : { duration: 2.4, repeat: Infinity, delay: (i * 0.17) % 1.6 }}
            className={`h-5 rounded-[5px] ${failed ? "bg-white/30" : "bg-white/80"}`}
          />
        ))}
      </div>

      <div className="mt-5 flex min-h-[34px] flex-wrap items-center gap-2">
        {failed && tenants.length === 0 && <p className="font-mono text-[12px] text-[var(--signal-bad)]">{cells.reroutedNote} →</p>}
        {tenants.map((t) => (
          <motion.span
            key={t}
            layoutId={`tenant-${t}`}
            transition={{ type: "spring", stiffness: 260, damping: 28 }}
            className="rounded-full border border-[rgba(255,181,71,0.4)] bg-[rgba(255,181,71,0.1)] px-3 py-1 font-mono text-[12px] text-[var(--beacon)]"
          >
            {t}
          </motion.span>
        ))}
      </div>
    </motion.div>
  );
}

export function Cells() {
  const { cells } = landing;
  const [failed, setFailed] = useState(false);
  const placement = (cell: number) => TENANTS.filter((t) => (failed ? 1 : t.home) === cell).map((t) => t.id);

  return (
    <section id={cells.id} aria-labelledby="cells-title" className="bg-black px-[var(--gutter)] py-[clamp(96px,16vh,180px)]">
      <div className="mx-auto grid max-w-[var(--content-max)] grid-cols-[0.9fr_1.1fr] items-center gap-[clamp(32px,6vw,96px)] max-[960px]:grid-cols-1">
        <Reveal>
          <p className="font-mono text-[12px] uppercase tracking-[0.22em] text-[var(--text-lo)]">{cells.eyebrow}</p>
          <h2 id="cells-title" className="mt-4 text-[clamp(30px,4vw,52px)] font-medium leading-[1.05] tracking-[-0.035em] text-white">
            {cells.title}
          </h2>
          <p className="mt-5 max-w-[48ch] text-[16px] leading-[1.6] text-[var(--text-mid)]">{cells.body}</p>
          <button
            type="button"
            aria-pressed={failed}
            onClick={() => setFailed((f) => !f)}
            className={`mt-8 inline-flex items-center gap-2 rounded-full px-5 py-3 text-[14px] font-semibold transition-all duration-300 hover:-translate-y-0.5 ${
              failed ? "bg-white text-black shadow-[var(--glow-cta)]" : "border border-[rgba(255,107,107,0.5)] text-[var(--signal-bad)] hover:bg-[rgba(255,107,107,0.08)]"
            }`}
          >
            {failed ? <RotateCcw aria-hidden className="size-4" /> : <Power aria-hidden className="size-4" />}
            {failed ? cells.toggleOff : cells.toggleOn}
          </button>
          <p className="sr-only" aria-live="polite">
            {failed ? cells.liveRegionFailed : cells.liveRegionRestored}
          </p>
        </Reveal>

        <Reveal delay={0.1}>
          <div className="relative rounded-[32px] border border-white/10 bg-[var(--ink-1)] p-[clamp(18px,3vw,32px)]">
            <div className="mx-auto flex w-fit items-center gap-3 rounded-full border border-white/15 bg-black px-4 py-2.5">
              <span className="grid size-7 place-items-center rounded-full bg-white text-black">
                <FleetMark className="size-[64%]" />
              </span>
              <span className="text-[14px] font-medium text-white">{cells.coordinator}</span>
            </div>
            <svg aria-hidden viewBox="0 0 400 60" preserveAspectRatio="none" className="h-14 w-full">
              <motion.path
                d="M200 0 C200 30 100 30 100 60"
                fill="none"
                strokeWidth="1.5"
                animate={{ stroke: failed ? "rgba(255,107,107,0.6)" : "rgba(255,255,255,0.35)", strokeDasharray: failed ? "4 6" : "0 0" }}
              />
              <path d="M200 0 C200 30 300 30 300 60" fill="none" stroke="rgba(255,255,255,0.35)" strokeWidth="1.5" />
            </svg>
            <LayoutGroup>
              <div className="grid grid-cols-2 gap-4 max-[520px]:grid-cols-1">
                <Cell index={0} failed={failed} tenants={placement(0)} />
                <Cell index={1} failed={false} tenants={placement(1)} />
              </div>
            </LayoutGroup>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
