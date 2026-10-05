"use client";

import { motion, useScroll, useTransform } from "motion/react";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { useEffect, useRef, useState } from "react";
import { useMediaQuery } from "@/lib/useMediaQuery";
import { Reveal } from "./Reveal";
import landing from "@/content/landing.json";

/** Pinned horizontal track on wide screens; an ordinary vertical list on narrow screens or reduced motion. */
export function LatencyTrace() {
  const { latency } = landing;
  const sectionRef = useRef<HTMLElement>(null);
  const trackRef = useRef<HTMLOListElement>(null);
  const reduced = usePrefersReducedMotion();
  const wide = useMediaQuery("(min-width: 901px)");
  const pinned = wide && !reduced;
  const [distance, setDistance] = useState(0);

  useEffect(() => {
    const track = trackRef.current;
    if (!track || !pinned) return;
    const measure = () => setDistance(Math.max(0, track.scrollWidth - window.innerWidth));
    measure();
    const ro = new ResizeObserver(measure);
    ro.observe(track);
    window.addEventListener("resize", measure);
    return () => {
      ro.disconnect();
      window.removeEventListener("resize", measure);
    };
  }, [pinned]);

  const { scrollYProgress } = useScroll({ target: sectionRef, offset: ["start start", "end end"] });
  const x = useTransform(scrollYProgress, [0.05, 0.95], [0, -distance]);
  const line = useTransform(scrollYProgress, [0.05, 0.95], [0, 1]);

  const header = (
    <Reveal className="px-[var(--gutter)]">
      <div className="mx-auto max-w-[var(--content-max)]">
        <p className="font-mono text-[12px] uppercase tracking-[0.22em] text-[var(--text-lo)]">{latency.eyebrow}</p>
        <h2 id="latency-title" className="mt-4 max-w-[760px] text-[clamp(30px,4vw,52px)] font-medium leading-[1.05] tracking-[-0.035em] text-white">
          {latency.title}
        </h2>
        <p className="mt-4 max-w-[560px] text-[16px] leading-[1.6] text-[var(--text-mid)]">{latency.note}</p>
      </div>
    </Reveal>
  );

  const stages = latency.stages.map((s, i) => (
    <li
      key={s.key}
      className={pinned ? "relative w-[min(420px,34vw)] shrink-0 pr-10" : "relative border-l border-white/15 pb-10 pl-6 last:pb-0"}
    >
      {pinned && <span aria-hidden className="absolute -top-[5px] left-0 size-[10px] rounded-full bg-[var(--beacon)] shadow-[0_0_18px_var(--beacon)]" />}
      {!pinned && <span aria-hidden className="absolute -left-[5px] top-1.5 size-[10px] rounded-full bg-[var(--beacon)]" />}
      <p className={`font-pixel text-[clamp(44px,5vw,72px)] leading-none text-white/15 ${pinned ? "mt-10" : ""}`}>{String(i + 1).padStart(2, "0")}</p>
      <p className="mt-4 font-mono text-[13px] text-[var(--beacon)]">{s.key}</p>
      <h3 className="mt-1 text-[22px] font-medium tracking-[-0.02em] text-white">{s.label}</h3>
      <p className="mt-2 max-w-[34ch] text-[15px] leading-[1.6] text-[var(--text-mid)]">{s.body}</p>
    </li>
  ));

  if (!pinned) {
    return (
      <section ref={sectionRef} id={latency.id} aria-labelledby="latency-title" className="bg-black py-[clamp(80px,14vh,160px)]">
        {header}
        <ol className="mx-auto mt-12 max-w-[var(--content-max)] px-[calc(var(--gutter)+6px)]">{stages}</ol>
      </section>
    );
  }

  return (
    <section ref={sectionRef} id={latency.id} aria-labelledby="latency-title" className="relative h-[320vh] bg-black">
      <div className="sticky top-0 flex h-[100svh] flex-col justify-center overflow-hidden">
        {header}
        <div className="relative mt-16">
          <div aria-hidden className="absolute inset-x-0 top-0 h-px bg-white/10" />
          <motion.div aria-hidden style={{ scaleX: line }} className="absolute inset-x-0 top-0 h-px origin-left bg-gradient-to-r from-[var(--beacon)] via-[var(--beacon)] to-[var(--signal-ok)]" />
          <motion.ol ref={trackRef} style={{ x }} className="flex w-max pl-[max(var(--gutter),calc((100vw-var(--content-max))/2+var(--gutter)))] pr-[30vw]">
            {stages}
          </motion.ol>
        </div>
      </div>
    </section>
  );
}
