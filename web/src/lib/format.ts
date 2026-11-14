import type { Period } from "../types";

/** Saturation point (|return| at which colour is fully intense) per period. */
const SCALE: Record<Period, number> = {
  "1D": 2, "1W": 4, "1M": 7, "3M": 12, "6M": 18, YTD: 25, "1Y": 30, "3Y": 60,
};
const DIFF_SCALE: Record<Period, number> = {   // yields: change in percentage points
  "1D": 0.15, "1W": 0.3, "1M": 0.5, "3M": 0.8, "6M": 1, YTD: 1.25, "1Y": 1.5, "3Y": 2.5,
};

/** How far a value sits towards its pole: which pole, and the % of pole colour mixed into the midpoint. */
function perfMix(v: number, period: Period, mode: "pct" | "diff"): { pole: "pos" | "neg"; pct: number } {
  const s = (mode === "diff" ? DIFF_SCALE : SCALE)[period];
  const t = Math.min(Math.abs(v) / s, 1);
  return { pole: v >= 0 ? "pos" : "neg", pct: Math.round(8 + Math.sqrt(t) * 62) }; // 8% → 70%; sqrt lifts small moves
}

/** Diverging background: neutral midpoint → pos/neg pole, intensity ∝ |v|. */
export function perfBg(v: number | null | undefined, period: Period, mode: "pct" | "diff" = "pct"): string {
  if (v == null || Number.isNaN(v)) return "transparent";
  const { pole, pct } = perfMix(v, period, mode);
  return `color-mix(in oklab, var(--${pole}) ${pct}%, var(--mid))`;
}

function hexToRgb(hex: string): [number, number, number] | null {
  const m = /^#([0-9a-f]{3}|[0-9a-f]{6})$/i.exec(hex.trim());
  if (!m) return null;
  const h = m[1].length === 3 ? m[1].replace(/./g, (c) => c + c) : m[1];
  return [0, 2, 4].map((i) => parseInt(h.slice(i, i + 2), 16)) as [number, number, number];
}

/**
 * Same scale as perfBg() but as a concrete rgb() string, for canvas charts that cannot
 * read CSS variables or color-mix(). Mixes in sRGB (perfBg mixes in oklab: near-identical).
 */
export function perfColor(
  v: number | null | undefined, period: Period, colors: { pos: string; neg: string; mid: string },
): string {
  const mid = hexToRgb(colors.mid);
  if (v == null || Number.isNaN(v) || !mid) return colors.mid;
  const { pole, pct } = perfMix(v, period, "pct");
  const p = hexToRgb(colors[pole]);
  if (!p) return colors.mid;
  const k = pct / 100;
  const [r, g, b] = p.map((c, i) => Math.round(c * k + mid[i] * (1 - k)));
  return `rgb(${r},${g},${b})`;
}

export function signed(v: number | null | undefined, decimals = 1, suffix = "%"): string {
  if (v == null || Number.isNaN(v)) return "–";
  const s = v > 0 ? "+" : v < 0 ? "−" : "";
  return `${s}${Math.abs(v).toFixed(decimals)}${suffix}`;
}

export function fmtReturn(v: number | null | undefined, mode: "pct" | "diff"): string {
  // yields change in pp → show basis points
  return mode === "diff" ? signed(v == null ? v : v * 100, 0, " bp") : signed(v, 1, "%");
}

export function fmtPrice(v: number | null | undefined): string {
  if (v == null) return "–";
  const abs = Math.abs(v);
  const d = abs >= 1000 ? 0 : abs >= 100 ? 1 : abs >= 10 ? 2 : abs >= 1 ? 3 : 4;
  return v.toLocaleString("en-US", { minimumFractionDigits: d, maximumFractionDigits: d });
}

export function fmtValue(v: number | null | undefined, decimals: number, units: string): string {
  if (v == null) return "–";
  const n = v.toLocaleString("en-US", { minimumFractionDigits: decimals, maximumFractionDigits: decimals });
  if (units === "%") return `${n}%`;
  if (units === "k" || units === "m") return `${n}${units}`;
  return n;
}

export function fmtDate(iso: string, opts: Intl.DateTimeFormatOptions = { month: "short", day: "numeric" }): string {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", { ...opts, timeZone: "UTC" });
}

export function relTime(iso: string): string {
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "–";
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 1) return "just now"; // also clamps future timestamps (clock skew, feed errors)
  if (mins < 60) return `${mins}m ago`;
  const h = Math.round(mins / 60);
  if (h < 48) return `${h}h ago`;
  return `${Math.round(h / 24)}d ago`;
}

/**
 * Signed compact count: −2.26M, +28k, −2.6k, +512. Rounds at each unit's
 * precision BEFORE picking the unit, so 999,600 → "+1.00M" (not "+1000k").
 */
export function signedCompact(v: number | null | undefined): string {
  if (v == null || Number.isNaN(v)) return "–";
  const round = (x: number, d: number) => Number(x.toFixed(d));
  const a = Math.abs(v);
  const s = v > 0 ? "+" : v < 0 ? "−" : "";
  if (round(a / 1e3, 0) >= 1e3) return `${s}${(a / 1e6).toFixed(2)}M`;
  if (round(a / 1e3, 1) >= 10) return `${s}${(a / 1e3).toFixed(0)}k`;
  if (round(a, 0) >= 1e3) return `${s}${(a / 1e3).toFixed(1)}k`;
  return `${s}${a.toFixed(0)}`;
}

/** The URL if it is http(s), else null (never render javascript:/data: links from feeds). */
export function safeUrl(u: string | null | undefined): string | null {
  if (!u) return null;
  try {
    const url = new URL(u);
    return url.protocol === "http:" || url.protocol === "https:" ? url.href : null;
  } catch {
    return null;
  }
}

/** "1st", "22nd", "73rd", "100th". */
export function ordinal(n: number): string {
  const r = Math.round(n);
  const t = r % 100;
  const sfx = t >= 11 && t <= 13 ? "th" : ({ 1: "st", 2: "nd", 3: "rd" } as Record<number, string>)[r % 10] ?? "th";
  return `${r}${sfx}`;
}
