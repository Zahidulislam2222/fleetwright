"use client";

import { motion, useScroll, useTransform, type MotionValue } from "motion/react";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { useRef } from "react";
import { AgentFragment, ClaimerFragment, CrawlerFragment } from "./WorkerFragments";
import { Reveal } from "./Reveal";
import { useMediaQuery } from "@/lib/useMediaQuery";
import landing from "@/content/landing.json";

const fragmentFor: Record<string, () => React.ReactElement> = {
  claimer: ClaimerFragment,
  crawler: CrawlerFragment,
  agent: AgentFragment,
};

type Card = (typeof landing.workers.cards)[number];

function StackCard({ card, index, count, progress, stacked }: { card: Card; index: number; count: number; progress: MotionValue<number>; stacked: boolean }) {
  // Each card shrinks a little as later cards slide over it.
  const targetScale = 1 - (count - 1 - index) * 0.045;
  const scale = useTransform(progress, [index / count, 1], [1, targetScale]);
  const dim = useTransform(progress, [index / count, 1], [0, (count - 1 - index) * 0.18]);
  const Fragment = fragmentFor[card.id];

  return (
    <div
      className={stacked ? "sticky flex h-[86svh] items-start justify-center" : "flex justify-center"}
      style={stacked ? { top: `calc(104px + ${index * 22}px)` } : undefined}
    >
      <motion.article
        style={stacked ? { scale } : undefined}
        className="relative grid w-full origin-top grid-cols-[1.05fr_1fr] gap-[clamp(24px,4vw,56px)] overflow-hidden rounded-[32px] border border-white/10 bg-[var(--ink-1)] p-[clamp(24px,4vw,48px)] max-[900px]:grid-cols-1"
      >
        {stacked && <motion.div aria-hidden style={{ opacity: dim }} className="pointer-events-none absolute inset-0 z-10 bg-black" />}
        <div className="flex flex-col">
          <p className="font-mono text-[12px] uppercase tracking-[0.18em] text-[var(--beacon)]">{card.kicker}</p>
          <h3 className="mt-3 font-pixel text-[clamp(30px,3.6vw,48px)] leading-[1.05] tracking-[-0.03em] text-white">{card.title}</h3>
          <p className="mt-4 max-w-[46ch] text-[16px] leading-[1.6] text-[var(--text-mid)]">{card.body}</p>
          <ul className="mt-auto space-y-2.5 pt-8">
            {card.points.map((point) => (
              <li key={point} className="flex items-center gap-3 text-[14.5px] text-white">
                <span aria-hidden className="size-1.5 rounded-full bg-[var(--beacon)]" />
                {point}
              </li>
            ))}
          </ul>
        </div>
        <div className="flex items-center">
          {Fragment && <Fragment />}
        </div>
      </motion.article>
    </div>
  );
}

/** Stacking narrative cards: sticky overlap on desktop, a plain list on narrow screens / reduced motion. */
export function WorkerStack() {
  const { workers } = landing;
  const ref = useRef<HTMLDivElement>(null);
  const reduced = usePrefersReducedMotion();
  const wide = useMediaQuery("(min-width: 901px)");
  const stacked = wide && !reduced;
  const { scrollYProgress } = useScroll({ target: ref, offset: ["start start", "end end"] });

  return (
    <section id={workers.id} aria-labelledby="workers-title" className="relative bg-black px-[var(--gutter)] pb-[clamp(80px,14vh,160px)] pt-[clamp(96px,16vh,180px)]">
      <div className="mx-auto max-w-[var(--content-max)]">
        <Reveal>
          <p className="font-mono text-[12px] uppercase tracking-[0.22em] text-[var(--text-lo)]">{workers.eyebrow}</p>
          <h2 id="workers-title" className="mt-4 max-w-[760px] text-[clamp(30px,4vw,52px)] font-medium leading-[1.05] tracking-[-0.035em] text-white">
            {workers.title}
          </h2>
          <p className="mt-4 max-w-[620px] text-[15px] leading-[1.6] text-[var(--text-mid)]">{workers.note}</p>
        </Reveal>
        <div ref={ref} className={`mt-14 ${stacked ? "space-y-[12vh]" : "space-y-6"}`}>
          {workers.cards.map((card, i) => (
            <StackCard key={card.id} card={card} index={i} count={workers.cards.length} progress={scrollYProgress} stacked={stacked} />
          ))}
        </div>
      </div>
    </section>
  );
}
