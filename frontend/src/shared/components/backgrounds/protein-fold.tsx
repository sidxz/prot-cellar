"use client";

import { useEffect, useRef } from "react";

/* ProtCellar auth cover — a procedurally-folded Cα backbone rotating in 3D.
   α-helix runs joined by turns, packed globular, with a few long-range tertiary
   contacts. Residues are colored N-terminus → C-terminus along the shared brand
   spectrum: both the LogoMark's gradient and the convention structural biologists
   use to rainbow a chain. Cursor tilts the fold and lights up nearby residues.
   Self-contained canvas, no deps; sits on its own dark ground so it's theme-agnostic
   (the auth screens are always dark). Sibling to chem-cellar's GridMotion cover. */

type V3 = [number, number, number];
type RGB = [number, number, number];

const TAU = Math.PI * 2;

// N → C stops, matching the LogoMark gradient.
const STOPS: Array<[number, number, number, number]> = [
  [0.0, 0x37, 0xd7, 0xfa],
  [0.4, 0x4b, 0x72, 0xfe],
  [0.68, 0xff, 0x8d, 0xf2],
  [1.0, 0xff, 0x87, 0x05],
];

/** Sample the brand spectrum at t ∈ [0,1]. Exported for a unit check. */
export function spectrum(t: number): RGB {
  const c = t < 0 ? 0 : t > 1 ? 1 : t;
  for (let i = 0; i < STOPS.length - 1; i++) {
    const a = STOPS[i];
    const b = STOPS[i + 1];
    if (c <= b[0]) {
      const f = (c - a[0]) / (b[0] - a[0]);
      return [
        Math.round(a[1] + (b[1] - a[1]) * f),
        Math.round(a[2] + (b[2] - a[2]) * f),
        Math.round(a[3] + (b[3] - a[3]) * f),
      ];
    }
  }
  const l = STOPS[STOPS.length - 1];
  return [l[1], l[2], l[3]];
}

const rgba = (c: RGB, a: number) => `rgba(${c[0]}, ${c[1]}, ${c[2]}, ${a})`;
const clamp = (v: number, lo: number, hi: number) => (v < lo ? lo : v > hi ? hi : v);

// Deterministic PRNG so the fold is the same shape on every load.
function mulberry32(seed: number) {
  let a = seed >>> 0;
  return () => {
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const N = 90;

// Build a compact pseudo-fold once: helix runs + turns, contracted toward the
// centroid each segment so it stays globular rather than wandering off.
function buildFold(): { res: V3[]; contacts: Array<[number, number]> } {
  const rand = mulberry32(0x50726f74); // "Prot"
  const res: V3[] = [];
  let cl: V3 = [0, 0, 0];
  let axis: V3 = [1, 0, 0];
  let per1: V3 = [0, 1, 0];
  let per2: V3 = [0, 0, 1];
  let ang = 0;
  let left = 0;

  const unit = (): V3 => {
    const v: V3 = [rand() - 0.5, rand() - 0.5, rand() - 0.5];
    const m = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / m, v[1] / m, v[2] / m];
  };
  const cross = (a: V3, b: V3): V3 => [
    a[1] * b[2] - a[2] * b[1],
    a[2] * b[0] - a[0] * b[2],
    a[0] * b[1] - a[1] * b[0],
  ];
  const norm = (v: V3): V3 => {
    const m = Math.hypot(v[0], v[1], v[2]) || 1;
    return [v[0] / m, v[1] / m, v[2] / m];
  };
  const newSeg = () => {
    cl = [cl[0] * 0.55, cl[1] * 0.55, cl[2] * 0.55];
    axis = unit();
    per1 = norm(cross(axis, unit()));
    per2 = cross(axis, per1);
    ang = rand() * TAU;
    left = 7 + Math.floor(rand() * 8);
  };

  newSeg();
  const rise = 1.25;
  const radius = 2.05;
  const step = 2.05;
  for (let i = 0; i < N; i++) {
    if (left <= 0) {
      cl = [
        cl[0] + axis[0] * rise * 1.6,
        cl[1] + axis[1] * rise * 1.6,
        cl[2] + axis[2] * rise * 1.6,
      ];
      newSeg();
    }
    ang += step;
    cl = [cl[0] + axis[0] * rise, cl[1] + axis[1] * rise, cl[2] + axis[2] * rise];
    const c = Math.cos(ang) * radius;
    const s = Math.sin(ang) * radius;
    res.push([
      cl[0] + per1[0] * c + per2[0] * s,
      cl[1] + per1[1] * c + per2[1] * s,
      cl[2] + per1[2] * c + per2[2] * s,
    ]);
    left--;
  }

  // Center on the centroid, normalize to unit radius.
  let cx = 0;
  let cy = 0;
  let cz = 0;
  for (const r of res) {
    cx += r[0];
    cy += r[1];
    cz += r[2];
  }
  cx /= N;
  cy /= N;
  cz /= N;
  let maxr = 0;
  for (const r of res) {
    r[0] -= cx;
    r[1] -= cy;
    r[2] -= cz;
    maxr = Math.max(maxr, Math.hypot(r[0], r[1], r[2]));
  }
  for (const r of res) {
    r[0] /= maxr;
    r[1] /= maxr;
    r[2] /= maxr;
  }

  // A handful of tertiary contacts (close in space, far in sequence).
  const contacts: Array<[number, number]> = [];
  for (let a = 0; a < N && contacts.length < 16; a++) {
    for (let b = a + 7; b < N; b++) {
      const dx = res[a][0] - res[b][0];
      const dy = res[a][1] - res[b][1];
      const dz = res[a][2] - res[b][2];
      if (dx * dx + dy * dy + dz * dz < 0.09) {
        contacts.push([a, b]);
        if (contacts.length >= 16) break;
      }
    }
  }
  return { res, contacts };
}

export function ProteinFold() {
  const canvasRef = useRef<HTMLCanvasElement>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const { res, contacts } = buildFold();
    const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    let w = 0;
    let h = 0;
    let rect = canvas.getBoundingClientRect();
    const mouse = { x: -9999, y: -9999 };
    let curX = 0; // eased tilt
    let curY = 0;
    let raf = 0;

    const proj = new Array<{ x: number; y: number; z: number; d: number }>(N);
    const order = Array.from({ length: N }, (_, i) => i);

    const draw = (time: number) => {
      if (!w || !h) return;
      const valid = mouse.x > -9000;
      const tx =
        valid && rect.width ? clamp((mouse.x - rect.left) / rect.width - 0.5, -0.7, 0.7) : 0;
      const ty =
        valid && rect.height ? clamp((mouse.y - rect.top) / rect.height - 0.5, -0.7, 0.7) : 0;
      curX += (tx - curX) * 0.08;
      curY += (ty - curY) * 0.08;

      ctx.clearRect(0, 0, w, h);
      const g = ctx.createRadialGradient(w / 2, h / 2, 0, w / 2, h / 2, Math.max(w, h) * 0.55);
      g.addColorStop(0, "rgba(46, 86, 150, 0.28)");
      g.addColorStop(1, "rgba(6, 10, 24, 0)");
      ctx.fillStyle = g;
      ctx.fillRect(0, 0, w, h);

      const ry = (reduce ? 0.7 : time * 0.00022) + curX * 1.15;
      const rx = -curY * 0.85 + 0.28;
      const cyo = Math.cos(ry);
      const syo = Math.sin(ry);
      const cxo = Math.cos(rx);
      const sxo = Math.sin(rx);
      const scale = Math.min(w, h) * 0.4;
      const ox = w / 2;
      const oy = h / 2;
      const cam = 3.3;

      for (let m = 0; m < N; m++) {
        const X = res[m][0];
        const Y = res[m][1];
        const Z = res[m][2];
        const x1 = X * cyo + Z * syo;
        const z1 = -X * syo + Z * cyo;
        const y1 = Y * cxo - z1 * sxo;
        const z2 = Y * sxo + z1 * cxo;
        const pv = cam / (cam - z2);
        proj[m] = { x: ox + x1 * scale * pv, y: oy + y1 * scale * pv, z: z2, d: pv };
      }

      ctx.lineCap = "round";
      // Backbone (drawn in chain order — slight overlap error at crossings is invisible here).
      for (let e = 1; e < N; e++) {
        const A = proj[e - 1];
        const B = proj[e];
        const dn = clamp((B.d - 0.72) / 0.75, 0, 1);
        ctx.strokeStyle = rgba(spectrum(e / N), 0.22 + 0.6 * dn);
        ctx.lineWidth = Math.max(0.6, 2.1 * B.d);
        ctx.beginPath();
        ctx.moveTo(A.x, A.y);
        ctx.lineTo(B.x, B.y);
        ctx.stroke();
      }
      // Tertiary contacts.
      for (const [i, j] of contacts) {
        const P = proj[i];
        const Q = proj[j];
        ctx.strokeStyle = `rgba(148, 180, 230, ${0.05 + 0.06 * Math.min(P.d, Q.d)})`;
        ctx.lineWidth = 0.7;
        ctx.beginPath();
        ctx.moveTo(P.x, P.y);
        ctx.lineTo(Q.x, Q.y);
        ctx.stroke();
      }
      // Residue nodes, back-to-front.
      order.sort((i, j) => proj[i].z - proj[j].z);
      const mxl = valid ? mouse.x - rect.left : -9999;
      const myl = valid ? mouse.y - rect.top : -9999;
      for (const idx of order) {
        const pr = proj[idx];
        const dn = clamp((pr.d - 0.72) / 0.75, 0, 1);
        const col = spectrum(idx / N);
        const near = Math.hypot(pr.x - mxl, pr.y - myl);
        const glow = near < 70 ? 1 - near / 70 : 0;
        const r = Math.max(0.8, (1.5 + 1.6 * dn) * pr.d) + glow * 2.4;
        if (glow > 0.02) {
          ctx.beginPath();
          ctx.arc(pr.x, pr.y, r + 5 * glow, 0, TAU);
          ctx.fillStyle = rgba(col, 0.14 * glow);
          ctx.fill();
        }
        ctx.beginPath();
        ctx.arc(pr.x, pr.y, r, 0, TAU);
        ctx.fillStyle = rgba(col, 0.4 + 0.5 * dn + 0.3 * glow);
        ctx.fill();
      }
    };

    const resize = () => {
      rect = canvas.getBoundingClientRect();
      w = rect.width;
      h = rect.height;
      if (!w || !h) return;
      const dpr = Math.min(2, window.devicePixelRatio || 1);
      canvas.width = Math.round(w * dpr);
      canvas.height = Math.round(h * dpr);
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      if (reduce) draw(0);
    };

    const onMove = (e: PointerEvent) => {
      mouse.x = e.clientX;
      mouse.y = e.clientY;
      rect = canvas.getBoundingClientRect();
    };
    const onLeave = () => {
      mouse.x = -9999;
      mouse.y = -9999;
    };

    const ro = new ResizeObserver(resize);
    ro.observe(canvas);
    resize();

    if (!reduce) {
      window.addEventListener("pointermove", onMove);
      document.addEventListener("mouseleave", onLeave);
      const render = (t: number) => {
        draw(t);
        raf = requestAnimationFrame(render);
      };
      raf = requestAnimationFrame(render);
    }

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      window.removeEventListener("pointermove", onMove);
      document.removeEventListener("mouseleave", onLeave);
    };
  }, []);

  return (
    <div
      className="relative h-full w-full overflow-hidden"
      aria-hidden="true"
      style={{ background: "radial-gradient(120% 100% at 50% 42%, #101d33 0%, #070b16 72%)" }}
    >
      <canvas ref={canvasRef} className="pointer-events-none absolute inset-0 h-full w-full" />
    </div>
  );
}
