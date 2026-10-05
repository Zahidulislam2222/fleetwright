"use client";

import { useMediaQuery } from "./useMediaQuery";

/**
 * Hydration-safe reduced-motion preference. Motion's useReducedMotion() differs between server
 * (null) and client (true/false), which made branches render different markup and broke hydration.
 * This returns false on the server and during hydration, then the real preference.
 */
export function usePrefersReducedMotion() {
  return useMediaQuery("(prefers-reduced-motion: reduce)");
}
