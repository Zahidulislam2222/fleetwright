"use client";

import { ReactLenis } from "lenis/react";
import { MotionConfig } from "motion/react";
import type { ReactNode } from "react";
import { smoothScroll } from "@/design/motion";

/**
 * Smooth wheel scrolling for the landing page only. Touch keeps native momentum (syncTouch off),
 * Lenis honours prefers-reduced-motion by itself, and anchor links glide with a header offset.
 */
export function SmoothScroll({ children }: { children: ReactNode }) {
  return (
    <ReactLenis
      root
      options={{
        lerp: smoothScroll.lerp,
        wheelMultiplier: smoothScroll.wheelMultiplier,
        touchMultiplier: smoothScroll.touchMultiplier,
        syncTouch: false,
        anchors: { offset: smoothScroll.anchorOffset },
        allowNestedScroll: true,
        autoRaf: true,
      }}
    >
      <MotionConfig reducedMotion="user">{children}</MotionConfig>
    </ReactLenis>
  );
}
