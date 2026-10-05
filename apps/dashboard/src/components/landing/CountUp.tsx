"use client";

import { animate, useInView } from "motion/react";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { useEffect, useRef, useState } from "react";

type Props = {
  value: number;
  decimals: number;
  prefix?: string;
  suffix?: string;
  delay: number;
  duration: number;
};

/** Counts from 0 to value once, when 25% visible (reference: easeOutCubic, staggered). */
export function CountUp({ value, decimals, prefix = "", suffix = "", delay, duration }: Props) {
  const ref = useRef<HTMLSpanElement>(null);
  const inView = useInView(ref, { once: true, amount: 0.25 });
  const reduced = usePrefersReducedMotion();
  const [display, setDisplay] = useState(0);

  useEffect(() => {
    if (!inView || reduced) return;
    const controls = animate(0, value, {
      delay,
      duration,
      ease: [0.33, 1, 0.68, 1],
      onUpdate: (v) => setDisplay(v),
    });
    return () => controls.stop();
  }, [inView, reduced, value, delay, duration]);

  const shown = reduced ? value : display;
  return (
    <span ref={ref} className="tabular">
      {prefix}
      {shown.toFixed(decimals)}
      {suffix}
    </span>
  );
}
