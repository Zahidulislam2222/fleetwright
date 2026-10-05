"use client";

import { AnimatePresence, motion, useMotionValueEvent, useScroll } from "motion/react";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { useEffect, useRef, useState } from "react";
import { claimScene, STEP_STARTS } from "./config";
import { easeOutExpo } from "@/design/motion";
import landing from "@/content/landing.json";
import type { ClaimRaceScene } from "./scene";

const STATE_TONE: Record<string, string> = {
  DETECTED: "text-[var(--beacon)]",
  QUEUED: "text-white",
  LEASED: "text-[var(--beacon)]",
  ACTING: "text-[var(--signal-bad)]",
  CONFIRMED: "text-[var(--signal-ok)]",
};

function stepFor(p: number) {
  let index = 0;
  STEP_STARTS.forEach((start, i) => {
    if (p >= start) index = i;
  });
  return index;
}

export function ClaimRace() {
  const { claimRace } = landing;
  const trackRef = useRef<HTMLElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const progress = useRef(0);
  const reduced = usePrefersReducedMotion();
  const [step, setStep] = useState(0);
  const [webglFailed, setWebglFailed] = useState(false);

  const { scrollYProgress } = useScroll({ target: trackRef, offset: ["start start", "end end"] });
  useMotionValueEvent(scrollYProgress, "change", (v) => {
    progress.current = v;
    const next = stepFor(v);
    setStep((s) => (s === next ? s : next));
  });

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    let scene: ClaimRaceScene | null = null;
    let frame = 0;
    let visible = false;
    let shown = reduced ? 0.6 : 0;
    let cancelled = false;
    const start = performance.now();

    const resize = () => {
      const rect = canvas.getBoundingClientRect();
      scene?.resize(Math.max(1, rect.width), Math.max(1, rect.height));
      if (reduced && scene) scene.render(shown, 0);
    };

    let last = performance.now();
    const loop = (now: number) => {
      if (!scene || !visible) return;
      // Ease toward the scroll target so fast wheel flicks still read as motion, not jumps.
      const dt = Math.min(0.25, (now - last) / 1000);
      last = now;
      const target = reduced ? 0.6 : progress.current;
      shown += (target - shown) * (1 - Math.exp(-dt * claimScene.followRate));
      scene.render(shown, reduced ? 0 : (now - start) / 1000);
      // Reduced motion: one static frame, no running loop.
      if (!reduced) frame = requestAnimationFrame(loop);
    };

    const io = new IntersectionObserver(([entry]) => {
      visible = entry.isIntersecting;
      cancelAnimationFrame(frame);
      if (visible) {
        last = performance.now();
        frame = requestAnimationFrame(loop);
      }
    });

    import("./scene")
      .then(({ ClaimRaceScene }) => {
        if (cancelled) return;
        try {
          scene = new ClaimRaceScene(canvas);
        } catch {
          setWebglFailed(true);
          return;
        }
        resize();
        io.observe(canvas);
      })
      .catch(() => setWebglFailed(true));

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);

    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
      io.disconnect();
      ro.disconnect();
      scene?.dispose();
    };
  }, [reduced]);

  const active = claimRace.steps[step];

  return (
    <section
      ref={trackRef}
      id={claimRace.id}
      aria-labelledby="claim-title"
      className={`relative bg-black ${reduced ? "" : "h-[460vh] max-[720px]:h-[380vh]"}`}
    >
      <div className={reduced ? "relative min-h-[100svh] overflow-hidden" : "sticky top-0 h-[100svh] overflow-hidden"}>
        <canvas ref={canvasRef} aria-hidden className="absolute inset-0 size-full" />
        <div aria-hidden className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(0,0,0,0.85)_0%,rgba(0,0,0,0.35)_42%,transparent_65%)] max-[900px]:bg-[linear-gradient(0deg,rgba(0,0,0,0.92)_0%,rgba(0,0,0,0.5)_40%,transparent_65%)]" />

        <div className={`relative mx-auto flex max-w-[var(--content-max)] flex-col justify-center px-[var(--gutter)] ${reduced ? "min-h-[100svh] py-24" : "h-full max-[900px]:justify-end max-[900px]:pb-10"}`}>
          <p className="mb-4 font-mono text-[12px] uppercase tracking-[0.22em] text-[var(--text-lo)]">{claimRace.eyebrow}</p>
          <h2 id="claim-title" className="max-w-[520px] text-[clamp(30px,4vw,52px)] font-medium leading-[1.05] tracking-[-0.035em] text-white">
            {claimRace.title}
          </h2>

          {/* Current state readout */}
          <div className={`mt-8 flex items-center gap-3 ${reduced ? "hidden" : ""}`} aria-hidden>
            <span className="font-mono text-[11px] uppercase tracking-[0.2em] text-[var(--text-lo)]">{claimRace.stateLabel}</span>
            <AnimatePresence mode="popLayout" initial={false}>
              <motion.span
                key={active.state}
                initial={{ opacity: 0, y: 10, filter: "blur(4px)" }}
                animate={{ opacity: 1, y: 0, filter: "blur(0px)", transitionEnd: { filter: "none" } }}
                exit={{ opacity: 0, y: -10, filter: "blur(4px)" }}
                transition={{ duration: 0.35, ease: easeOutExpo }}
                className={`font-pixel text-[clamp(22px,2.6vw,32px)] ${STATE_TONE[active.state]}`}
              >
                {active.state}
              </motion.span>
            </AnimatePresence>
          </div>

          {/* Desktop: full ordered list, active step lit. Mobile: the active step only. */}
          {/* Reduced motion: the whole sequence, readable at every width (no scroll scrubbing). */}
          <ol className={`mt-6 max-w-[460px] space-y-1 ${reduced ? "" : "max-[900px]:hidden"}`}>
            {claimRace.steps.map((s, i) => (
              <li
                key={s.state}
                aria-current={i === step ? "step" : undefined}
                className="relative rounded-2xl py-3 pl-5 transition-colors duration-500"
              >
                <span
                  aria-hidden
                  className={`absolute left-0 top-[18px] h-[calc(100%-24px)] w-[2px] rounded-full transition-colors duration-500 ${i === step || reduced ? "bg-[var(--beacon)]" : i < step ? "bg-white/25" : "bg-white/10"}`}
                />
                <p className={`text-[15px] font-medium transition-colors duration-500 ${i === step || reduced ? "text-white" : "text-[var(--text-lo)]"}`}>
                  <span className="sr-only">{s.state}: </span>
                  {s.title}
                </p>
                <motion.div
                  initial={false}
                  animate={{ height: i === step || reduced ? "auto" : 0, opacity: i === step || reduced ? 1 : 0 }}
                  transition={{ duration: 0.45, ease: easeOutExpo }}
                  className="overflow-hidden"
                >
                  <p className="pt-1.5 text-[14px] leading-[1.6] text-[var(--text-mid)]">{s.body}</p>
                </motion.div>
              </li>
            ))}
          </ol>

          <div className={`mt-5 min-[901px]:hidden ${reduced ? "hidden" : ""}`} aria-live="polite">
            <AnimatePresence mode="wait" initial={false}>
              <motion.div
                key={active.state}
                initial={{ opacity: 0, y: 12 }}
                animate={{ opacity: 1, y: 0 }}
                exit={{ opacity: 0, y: -8 }}
                transition={{ duration: 0.3, ease: easeOutExpo }}
                className="rounded-2xl border border-white/10 bg-black/60 p-4 backdrop-blur-md"
              >
                <p className="text-[15px] font-medium text-white">{active.title}</p>
                <p className="mt-1.5 text-[14px] leading-[1.55] text-[var(--text-mid)]">{active.body}</p>
              </motion.div>
            </AnimatePresence>
            <div className="mt-3 flex gap-1.5" aria-hidden>
              {claimRace.steps.map((s, i) => (
                <span key={s.state} className={`h-1 flex-1 rounded-full transition-colors duration-500 ${i <= step ? "bg-[var(--beacon)]" : "bg-white/15"}`} />
              ))}
            </div>
          </div>

          {webglFailed && <p className="mt-6 max-w-[460px] text-[13px] text-[var(--text-lo)]">{claimRace.fallbackNote}</p>}
        </div>
      </div>
    </section>
  );
}
