"use client";

import Link from "next/link";
import { AnimatePresence, motion } from "motion/react";
import { useLenis } from "lenis/react";
import { useCallback, useEffect, useRef, useState } from "react";
import { FleetMark } from "@/components/brand/FleetMark";
import { easeOutExpo } from "@/design/motion";
import landing from "@/content/landing.json";

const MOBILE_QUERY = "(max-width: 720px)";

export function SiteHeader() {
  const { nav } = landing;
  const [open, setOpen] = useState(false);
  const [active, setActive] = useState<string>("");
  const burgerRef = useRef<HTMLButtonElement>(null);
  const lenis = useLenis();

  const close = useCallback(() => {
    setOpen(false);
    burgerRef.current?.focus();
  }, []);

  // Scroll-spy: mark the section currently under the header as active.
  useEffect(() => {
    const ids = nav.links.map((l) => l.href.replace("#", ""));
    const targets = ids.map((id) => document.getElementById(id)).filter((el): el is HTMLElement => !!el);
    if (!targets.length) return;
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.filter((e) => e.isIntersecting).sort((a, b) => b.intersectionRatio - a.intersectionRatio);
        if (visible[0]) setActive(`#${visible[0].target.id}`);
      },
      { rootMargin: "-40% 0px -50% 0px", threshold: [0, 0.25, 0.5] },
    );
    targets.forEach((t) => observer.observe(t));
    return () => observer.disconnect();
  }, [nav.links]);

  // Mobile sheet: Escape closes, resize past the breakpoint closes, body scroll locks while open.
  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && close();
    const mq = window.matchMedia(MOBILE_QUERY);
    const onChange = () => !mq.matches && setOpen(false);
    window.addEventListener("keydown", onKey);
    mq.addEventListener("change", onChange);
    lenis?.stop();
    return () => {
      window.removeEventListener("keydown", onKey);
      mq.removeEventListener("change", onChange);
      lenis?.start();
    };
  }, [open, close, lenis]);

  return (
    <header className="fixed inset-x-0 top-0 z-[var(--z-header)] px-[clamp(14px,3vw,32px)] pt-[clamp(14px,2.4vh,24px)]">
      <motion.div
        initial={{ opacity: 0, y: -18 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.7, ease: easeOutExpo }}
        className="mx-auto flex max-w-[760px] items-center justify-between gap-[clamp(14px,2.4vw,24px)] min-[721px]:justify-center"
      >
        <Link
          href="/"
          aria-label={`${nav.brand} home`}
          className="grid size-[clamp(42px,4.4vw,48px)] shrink-0 place-items-center rounded-full bg-white text-black shadow-[var(--shadow-soft)] transition-transform duration-200 hover:scale-[1.04]"
        >
          <FleetMark className="size-[62%]" />
        </Link>

        <nav aria-label={landing.nav.primaryLabel} className="on-light hidden h-[clamp(44px,5.2vw,48px)] max-w-[460px] flex-1 items-center justify-around rounded-full bg-white px-2 shadow-[var(--shadow-soft)] min-[721px]:flex">
          {nav.links.map((link) => {
            const isActive = active === link.href;
            return (
              <a
                key={link.href}
                href={link.href}
                aria-current={isActive ? "true" : undefined}
                className="relative px-2 py-3 text-[clamp(13px,1.4vw,15px)] font-medium tracking-[-0.01em] text-[var(--text-on-light-2)] transition-colors duration-200 hover:text-[var(--text-on-light)] aria-[current]:text-[var(--text-on-light)]"
              >
                {link.label}
                {isActive && (
                  <motion.span
                    layoutId="nav-dots"
                    aria-hidden
                    className="absolute bottom-[5px] left-1/2 size-[3px] -translate-x-1/2 rounded-full bg-black shadow-[-5px_0_0_#000,5px_0_0_#000]"
                    transition={{ type: "spring", stiffness: 500, damping: 38 }}
                  />
                )}
              </a>
            );
          })}
        </nav>

        <Link
          href={nav.cta.href}
          className="hidden h-[clamp(44px,5.2vw,48px)] items-center rounded-full bg-[var(--pill-dark)] px-6 text-[clamp(13px,1.4vw,15px)] font-medium text-[var(--sign-in-text)] shadow-[var(--shadow-soft)] transition-all duration-200 hover:-translate-y-px hover:bg-[var(--pill-dark-hover)] hover:text-white min-[721px]:inline-flex"
        >
          {nav.cta.label}
        </Link>

        <button
          ref={burgerRef}
          type="button"
          aria-expanded={open}
          aria-controls="mobile-menu"
          aria-label={open ? nav.closeLabel : nav.menuLabel}
          onClick={() => setOpen((v) => !v)}
          className={`relative grid size-12 place-items-center rounded-full transition-colors duration-200 min-[721px]:hidden ${open ? "on-light bg-white" : "bg-[var(--pill-dark)]"}`}
        >
          {[-6.5, 0, 6.5].map((offset, i) => (
            <span
              key={offset}
              aria-hidden
              className={`absolute h-[1.5px] w-[18px] rounded-full transition-all duration-300 ${open ? "bg-black" : "bg-white"}`}
              style={{
                transform: open
                  ? i === 1
                    ? "scaleX(0)"
                    : `translateY(0) rotate(${i === 0 ? 45 : -45}deg)`
                  : `translateY(${offset}px)`,
              }}
            />
          ))}
        </button>
      </motion.div>

      <AnimatePresence>
        {open && (
          <>
            <motion.div
              key="overlay"
              aria-hidden
              onClick={close}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.28 }}
              className="fixed inset-0 -z-10 bg-black/60 backdrop-blur-md"
            />
            <motion.nav
              key="sheet"
              id="mobile-menu"
              aria-label={landing.nav.mobileLabel}
              initial={{ opacity: 0, y: -12, scale: 0.97 }}
              animate={{ opacity: 1, y: 0, scale: 1 }}
              exit={{ opacity: 0, y: -8, scale: 0.98 }}
              transition={{ duration: 0.38, ease: easeOutExpo }}
              className="on-light mx-auto mt-3 max-w-[420px] rounded-[var(--radius-lg)] bg-white px-[18px] pb-5 pt-[22px] shadow-[0_20px_60px_rgba(0,0,0,0.45)]"
            >
              <ul className="flex flex-col">
                {nav.links.map((link, i) => (
                  <motion.li
                    key={link.href}
                    initial={{ opacity: 0, x: -8 }}
                    animate={{ opacity: 1, x: 0 }}
                    transition={{ delay: 0.06 + i * 0.05, duration: 0.3, ease: easeOutExpo }}
                  >
                    <a
                      href={link.href}
                      onClick={() => setOpen(false)}
                      className="block rounded-2xl px-4 py-3.5 text-lg font-medium tracking-[-0.01em] text-[var(--text-on-light)] hover:bg-black/5"
                    >
                      {link.label}
                    </a>
                  </motion.li>
                ))}
              </ul>
              <Link
                href={nav.cta.href}
                className="mt-3 flex h-12 items-center justify-center rounded-full bg-[var(--pill-dark)] font-medium text-white"
              >
                {nav.cta.label}
              </Link>
            </motion.nav>
          </>
        )}
      </AnimatePresence>
    </header>
  );
}
