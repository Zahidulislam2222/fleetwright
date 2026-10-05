"use client";

import { motion, useScroll, useTransform, type MotionValue } from "motion/react";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { useRef } from "react";
import landing from "@/content/landing.json";

function Word({ word, progress, range, emphasis }: { word: string; progress: MotionValue<number>; range: [number, number]; emphasis: boolean }) {
  const opacity = useTransform(progress, range, [0.14, 1]);
  // Fully revealed words drop the filter entirely (no idle compositing surfaces).
  const blur = useTransform(progress, (v) => {
    const t = Math.min(1, Math.max(0, (v - range[0]) / (range[1] - range[0])));
    return t >= 1 ? "none" : `blur(${(3 * (1 - t)).toFixed(2)}px)`;
  });
  return (
    <motion.span style={{ opacity, filter: blur }} className={emphasis ? "text-[var(--beacon)]" : undefined}>
      {word}{" "}
    </motion.span>
  );
}

/** Scroll-linked text reveal: each word lights up as the reader reaches it. Plain text without motion. */
export function ProblemReveal() {
  const { problem } = landing;
  const ref = useRef<HTMLDivElement>(null);
  const reduced = usePrefersReducedMotion();
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start 0.85", "end 0.55"] });
  const words = problem.text.split(" ");
  const emphasis = new Set(problem.emphasis.map((w) => w.toLowerCase()));

  return (
    <section aria-labelledby="problem-eyebrow" className="relative bg-black px-[var(--gutter)] py-[clamp(96px,18vh,200px)]">
      <div ref={ref} className="mx-auto max-w-[1080px]">
        <p id="problem-eyebrow" className="mb-8 font-mono text-[12px] uppercase tracking-[0.22em] text-[var(--text-lo)]">
          {problem.eyebrow}
        </p>
        <p className="text-[clamp(28px,4.6vw,60px)] font-medium leading-[1.12] tracking-[-0.035em] text-white">
          {reduced
            ? problem.text
            : words.map((word, i) => {
                const start = i / words.length;
                const clean = word.replace(/[^a-z]/gi, "").toLowerCase();
                return (
                  <Word
                    key={`${word}-${i}`}
                    word={word}
                    progress={scrollYProgress}
                    range={[start, Math.min(1, start + 2.5 / words.length)]}
                    emphasis={emphasis.has(clean)}
                  />
                );
              })}
        </p>
      </div>
    </section>
  );
}
