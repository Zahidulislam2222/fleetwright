/**
 * Motion tokens for Motion for React. CSS transitions use the matching custom properties in
 * globals.css (--ease-out-expo, --dur-*); keep the two in step when either changes.
 */
export const easeOutExpo = [0.22, 1, 0.36, 1] as const;
export const easeInOut = [0.65, 0, 0.35, 1] as const;

export const duration = {
  fast: 0.16,
  base: 0.28,
  slow: 0.85,
} as const;

/**
 * The reference's shared entrance: rise 22px, scale 0.98, blur 6px → settled.
 * transitionEnd clears the filter: a leftover `blur(0px)` keeps a compositing surface alive and,
 * inside sticky sections, stalled Chrome rendering (found in verification, 2026-10-05).
 */
export const riseIn = {
  hidden: { opacity: 0, y: 22, scale: 0.98, filter: "blur(6px)" },
  shown: { opacity: 1, y: 0, scale: 1, filter: "blur(0px)", transitionEnd: { filter: "none" } },
} as const;

/** Smooth-scroll feel (Lenis). Lower lerp = longer glide. */
export const smoothScroll = {
  lerp: 0.085,
  wheelMultiplier: 1,
  touchMultiplier: 1,
  anchorOffset: -96,
} as const;
