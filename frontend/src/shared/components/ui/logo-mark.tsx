"use client";

import { useId } from "react";

/* protcellar α-helix mark — sibling to docu-store's "cited compound".
   One continuous coil (bold ~300° loops) with faint threads passing behind
   through the gaps: reads as a protein α-helix, not stacked rings. The strand
   carries the shared brand gradient; the whole mark is self-colored, so it sits
   on any background with no theme handling. Canonical source: src/app/icon.svg. */
export function LogoMark({ className }: { className?: string }) {
  const id = useId();
  return (
    <svg viewBox="0 0 32 32" className={className} aria-hidden="true">
      <defs>
        <linearGradient
          id={id}
          gradientUnits="userSpaceOnUse"
          x1="6"
          y1="24"
          x2="28"
          y2="6"
        >
          <stop offset="0" stopColor="#37d7fa" />
          <stop offset="0.4" stopColor="#4b72fe" />
          <stop offset="0.68" stopColor="#ff8df2" />
          <stop offset="1" stopColor="#ff8705" />
        </linearGradient>
      </defs>
      <g fill="none" stroke={`url(#${id})`} strokeLinecap="round">
        {/* strand passing behind, through the coil gaps */}
        <path
          d="M13 5.7 L19 10.7 M13 10.7 L19 15.7 M13 15.7 L19 20.7"
          strokeWidth="1.4"
          opacity="0.4"
        />
        {/* the coil (front) */}
        <path
          d="M19 5.7 A6 3 0 1 1 13 5.7 M19 10.7 A6 3 0 1 1 13 10.7 M19 15.7 A6 3 0 1 1 13 15.7 M19 20.7 A6 3 0 1 1 13 20.7"
          strokeWidth="2"
        />
      </g>
    </svg>
  );
}
