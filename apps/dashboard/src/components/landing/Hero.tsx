"use client";

import Link from "next/link";
import { motion, useScroll, useTransform } from "motion/react";
import { usePrefersReducedMotion } from "@/lib/usePrefersReducedMotion";
import { Bot, CircleDashed, Crosshair, Pause, Play, Radar, type LucideIcon } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { CountUp } from "./CountUp";
import { easeOutExpo, riseIn } from "@/design/motion";
import landing from "@/content/landing.json";
import media from "@/content/media.json";

const workerIcons: Record<string, LucideIcon> = { crawler: Radar, claimer: Crosshair, agent: Bot };

function rise(delay: number) {
  return {
    initial: riseIn.hidden,
    animate: riseIn.shown,
    transition: { duration: 0.85, ease: easeOutExpo, delay },
  };
}

export function Hero() {
  const { hero } = landing;
  const sectionRef = useRef<HTMLElement>(null);
  const videoRef = useRef<HTMLVideoElement>(null);
  const reduced = usePrefersReducedMotion();
  const [videoFailed, setVideoFailed] = useState(false);
  // WCAG 2.2.2: moving content that lasts > 5 s needs a pause control. null = follow the default.
  const [userPaused, setUserPaused] = useState<boolean | null>(null);
  const paused = userPaused ?? reduced;

  // As the hero leaves, the film sinks and dims slightly — the page "dives" into the story.
  const { scrollYProgress } = useScroll({ target: sectionRef, offset: ["start start", "end start"] });
  const filmScale = useTransform(scrollYProgress, [0, 1], [1, 1.12]);
  const filmY = useTransform(scrollYProgress, [0, 1], ["0%", "12%"]);
  const contentY = useTransform(scrollYProgress, [0, 1], ["0%", "-18%"]);
  const contentOpacity = useTransform(scrollYProgress, [0, 0.7], [1, 0]);

  // Video failure → poster <img>. The server-rendered <video> can fail before hydration, when no React
  // handler exists yet, so check networkState on mount and listen natively on the last <source>.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    const sources = video.querySelectorAll("source");
    const last = sources[sources.length - 1];
    const fail = () => setVideoFailed(true);
    let frame = 0;
    if (video.networkState === HTMLMediaElement.NETWORK_NO_SOURCE) frame = requestAnimationFrame(fail);
    last?.addEventListener("error", fail);
    return () => {
      cancelAnimationFrame(frame);
      last?.removeEventListener("error", fail);
    };
  }, []);

  // Play only when allowed (not paused by the viewer or by reduced motion) and on screen.
  // No autoPlay attribute: the server markup must not start motion before the preference is known.
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;
    if (paused) {
      video.pause();
      return;
    }
    const io = new IntersectionObserver(([entry]) => {
      if (entry.isIntersecting) video.play().catch(() => undefined);
      else video.pause();
    });
    io.observe(video);
    return () => io.disconnect();
  }, [paused]);

  return (
    <section
      ref={sectionRef}
      aria-labelledby="hero-title"
      className="relative isolate flex h-[100svh] min-h-[640px] flex-col overflow-hidden bg-black"
    >
      {/* Film */}
      <motion.div
        aria-hidden
        style={reduced ? undefined : { scale: filmScale, y: filmY }}
        className="absolute inset-0 -z-10 origin-center"
      >
        {!videoFailed ? (
          <video
            ref={videoRef}
            className="size-full object-cover"
            muted
            loop
            playsInline
            preload="metadata"
            poster={media.hero.poster}
          >
            <source src={media.hero.videoMobile} type="video/mp4" media="(max-width: 720px)" />
            <source src={media.hero.video} type="video/mp4" />
          </video>
        ) : (
          // eslint-disable-next-line @next/next/no-img-element -- decorative poster fallback, sized by its container
          <img src={media.hero.poster} alt="" className="size-full object-cover" />
        )}
        {/* Legibility scrims: keep the stats and nav readable over bright vessels */}
        <div className="absolute inset-0 bg-[radial-gradient(ellipse_70%_45%_at_50%_48%,rgba(0,0,0,0.42),transparent_70%)]" />
        <div className="absolute inset-x-0 top-0 h-40 bg-gradient-to-b from-black/70 to-transparent" />
        <div className="absolute inset-x-0 bottom-0 h-[46%] bg-gradient-to-t from-black via-black/70 to-transparent" />
      </motion.div>

      <motion.div
        style={reduced ? undefined : { y: contentY, opacity: contentOpacity }}
        className="flex flex-1 flex-col items-center px-[clamp(14px,3vw,32px)] pb-[clamp(20px,3.4vh,36px)] pt-[clamp(88px,13vh,128px)]"
      >
        {/* Hero centre */}
        <div className="flex max-w-[960px] flex-1 flex-col items-center justify-center text-center">
          <motion.div {...rise(0.05)} className="mb-[clamp(16px,2.5vh,26px)] flex items-center">
            {hero.workerTypes.map((w, i) => {
              const Icon = workerIcons[w.id] ?? CircleDashed;
              return (
                <span
                  key={w.id}
                  title={w.label}
                  className="relative grid size-[clamp(36px,4.5vw,42px)] place-items-center rounded-full border border-[var(--hairline-strong)] bg-[var(--pill-dark)] p-[5px] transition-transform duration-300 hover:-translate-y-1"
                  style={{ marginLeft: i === 0 ? 0 : "calc(clamp(36px,4.5vw,42px) * -0.42)", zIndex: [1, 2, 4][i] }}
                >
                  <span className="grid size-full place-items-center rounded-full bg-white text-[#111]">
                    <Icon aria-hidden className="size-[52%]" strokeWidth={2.2} />
                  </span>
                  <span className="sr-only">{w.label}</span>
                </span>
              );
            })}
            <span
              className="flex h-[clamp(36px,4.5vw,42px)] items-center rounded-full border border-[var(--hairline-strong)] bg-[var(--pill-dark)] pr-4 text-[clamp(12px,1.4vw,13.5px)] font-medium text-[#c4c2c3]"
              style={{ marginLeft: "calc(clamp(36px,4.5vw,42px) * -0.42)", paddingLeft: "calc(clamp(36px,4.5vw,42px) * 0.58)" }}
            >
              {hero.badge}
            </span>
          </motion.div>

          <h1 id="hero-title" className="font-pixel text-[clamp(30px,6.4vw,84px)] leading-[1.1] tracking-[-0.03em] text-white max-[720px]:tracking-[-0.05em]">
            {hero.headline.map((line, i) => (
              <motion.span
                key={line}
                className="block whitespace-nowrap"
                initial={{ opacity: 0, y: 14 }}
                animate={{ opacity: 1, y: 0 }}
                transition={{ duration: 0.85, ease: easeOutExpo, delay: 0.12 + i * 0.18 }}
              >
                {line}
              </motion.span>
            ))}
          </h1>

          <motion.p
            {...rise(0.28)}
            className="mt-[clamp(14px,2.4vh,22px)] max-w-[min(540px,92%)] text-[clamp(15px,1.55vw,18.5px)] leading-[1.55] text-[var(--text-mid)]/85"
          >
            {hero.subhead}
          </motion.p>

          <motion.div
            initial={{ opacity: 0, y: 22, scale: 0.94, filter: "blur(6px)" }}
            animate={{ opacity: 1, y: 0, scale: [0.94, 1.04, 1], filter: "blur(0px)", transitionEnd: { filter: "none" } }}
            transition={{ duration: 0.95, ease: easeOutExpo, delay: 0.4 }}
            className="mt-[clamp(18px,3vh,30px)]"
          >
            <Link
              href={hero.cta.href}
              className="inline-flex items-center rounded-full bg-white px-[clamp(22px,3vw,28px)] py-[clamp(11px,1.6vh,13px)] text-[clamp(13.5px,1.5vw,14.5px)] font-semibold text-black shadow-[var(--glow-cta)] transition-[transform,box-shadow] duration-300 hover:-translate-y-0.5 hover:scale-[1.02] hover:shadow-[var(--glow-cta-hover)]"
            >
              {hero.cta.label}
            </Link>
          </motion.div>
        </div>

        {/* Stats footer */}
        <div className="w-full max-w-[940px]">
          <dl className="grid grid-cols-4 gap-x-4 gap-y-6 max-[720px]:grid-cols-2">
            {hero.stats.map((s, i) => (
              <motion.div key={s.label} {...rise(0.5 + i * 0.08)} className="flex flex-col items-center gap-1.5 text-center">
                <span aria-hidden className="font-pixel text-[clamp(22px,3vw,33px)] leading-none text-white">
                  {s.glyph}
                </span>
                <dt className="order-3 text-[clamp(11.5px,1.2vw,12.5px)] text-[var(--text-lo)]">{s.label}</dt>
                <dd className="order-2 text-[clamp(18px,2.2vw,26px)] font-medium tracking-[-0.025em] text-white">
                  <CountUp
                    value={s.value}
                    decimals={s.decimals}
                    prefix={s.prefix}
                    suffix={s.suffix}
                    delay={0.48 + i * 0.09}
                    duration={1.5 + i * 0.08}
                  />
                </dd>
              </motion.div>
            ))}
          </dl>
          <motion.p {...rise(0.85)} className="mt-4 text-center text-[11.5px] text-[var(--text-lo)]">
            {hero.statsCaption}
          </motion.p>
        </div>
      </motion.div>
      {!videoFailed && (
        <button
          type="button"
          onClick={() => setUserPaused(!paused)}
          aria-pressed={paused}
          className="absolute bottom-5 right-[var(--gutter)] z-[var(--z-content)] grid size-10 place-items-center rounded-full border border-white/20 bg-black/50 text-white backdrop-blur-md transition-colors hover:bg-black/70"
        >
          {paused ? <Play aria-hidden className="size-4" /> : <Pause aria-hidden className="size-4" />}
          <span className="sr-only">{paused ? hero.videoPlay : hero.videoPause}</span>
        </button>
      )}
    </section>
  );
}
