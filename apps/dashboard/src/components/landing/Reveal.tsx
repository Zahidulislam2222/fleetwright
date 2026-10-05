"use client";

import { motion } from "motion/react";
import type { ReactNode } from "react";
import { easeOutExpo, riseIn } from "@/design/motion";

/** Finite entrance when the block first enters the viewport (the reference's blur-rise). */
export function Reveal({ children, delay = 0, className }: { children: ReactNode; delay?: number; className?: string }) {
  return (
    <motion.div
      className={className}
      initial={riseIn.hidden}
      whileInView={riseIn.shown}
      viewport={{ once: true, amount: 0.3 }}
      transition={{ duration: 0.85, ease: easeOutExpo, delay }}
    >
      {children}
    </motion.div>
  );
}
