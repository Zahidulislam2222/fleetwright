"use client";

import { useEffect, useRef, useState, type RefObject } from "react";

const FOCUSABLE = 'a[href],button:not([disabled]),input:not([disabled]),select:not([disabled]),textarea:not([disabled]),[tabindex]:not([tabindex="-1"])';

/**
 * Modal dialog behaviour: focus moves inside on open (and again whenever `focusKey` changes, e.g. a
 * multi-step dialog swapping its content), Tab is trapped, Escape closes, and focus returns to the
 * element that opened the dialog when it unmounts.
 */
export function useDialog(
  ref: RefObject<HTMLElement | null>,
  onClose: () => void,
  focusKey?: string,
  /** Where focus goes on close if the opener no longer exists (e.g. a "Book" button replaced by "Booked"). */
  fallbackFocus?: () => HTMLElement | null,
) {
  // Captured at first render, before any effect moves focus into the dialog. Capturing it inside
  // the effect breaks under StrictMode: the re-run effect would record an element inside the dialog.
  // <body> is not an opener: Safari does not focus a clicked button, so activeElement stays on body.
  const [opener] = useState(() => {
    if (typeof document === "undefined") return null;
    const el = document.activeElement as HTMLElement | null;
    return el && el !== document.body ? el : null;
  });
  const closeRef = useRef(onClose);
  const fallbackRef = useRef(fallbackFocus);
  useEffect(() => {
    closeRef.current = onClose;
    fallbackRef.current = fallbackFocus;
  }, [onClose, fallbackFocus]);

  // Open / close: remember the opener, trap Tab, close on Escape, restore focus.
  useEffect(() => {
    const node = ref.current;
    const onKey = (e: KeyboardEvent) => {
      const root = ref.current;
      if (!root) return;
      if (e.key === "Escape") {
        e.preventDefault();
        closeRef.current();
        return;
      }
      if (e.key !== "Tab") return;
      const items = [...root.querySelectorAll<HTMLElement>(FOCUSABLE)];
      if (items.length === 0) {
        e.preventDefault();
        return;
      }
      const first = items[0];
      const last = items[items.length - 1];
      const inside = root.contains(document.activeElement);
      if (e.shiftKey && (document.activeElement === first || !inside)) {
        e.preventDefault();
        last.focus();
      } else if (!e.shiftKey && (document.activeElement === last || !inside)) {
        e.preventDefault();
        first.focus();
      }
    };
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("keydown", onKey);
      // Defer one frame so the opener's replacement (if any) has rendered.
      requestAnimationFrame(() => {
        // Still mounted (StrictMode's simulated unmount): leave focus inside the dialog.
        if (node?.isConnected) return;
        // The opener can exist yet be unfocusable (e.g. hidden by a breakpoint) — then use the fallback.
        opener?.focus();
        if (!opener || document.activeElement !== opener) fallbackRef.current?.()?.focus();
      });
    };
  }, [ref, opener]);

  // Initial focus, and refocus when the dialog's content step changes.
  useEffect(() => {
    ref.current?.querySelector<HTMLElement>(FOCUSABLE)?.focus();
  }, [ref, focusKey]);
}
