"use client";

import { useCallback, useRef, useState } from "react";

/**
 * Track a container element's content width in px, updating on resize.
 *
 * Charts render their SVG at this width with viewBox = the same width (1:1), so
 * font sizes and marks stay a fixed pixel size on any monitor and only the plot
 * area stretches — instead of a fixed viewBox scaling the whole chart up on wide
 * screens.
 *
 * Uses a **callback ref** (not useEffect) so the ResizeObserver attaches whenever
 * the element actually mounts — including elements that appear later, e.g. after
 * an async fetch resolves. Returns a fallback width before measurement (and in
 * jsdom/SSR, where ResizeObserver is unavailable).
 */
export function useMeasuredWidth<T extends HTMLElement>(
  fallback = 640,
): [(el: T | null) => void, number] {
  const [width, setWidth] = useState(fallback);
  const observerRef = useRef<ResizeObserver | null>(null);

  const ref = useCallback((el: T | null) => {
    observerRef.current?.disconnect();
    observerRef.current = null;
    if (!el || typeof ResizeObserver === "undefined") return;
    const update = () => {
      const w = el.clientWidth;
      if (w > 0) setWidth(w);
    };
    update();
    const ro = new ResizeObserver(update);
    ro.observe(el);
    observerRef.current = ro;
  }, []);

  return [ref, width];
}
