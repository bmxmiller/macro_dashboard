import type { EChartsOption } from "echarts";   // type-only: erased, keeps tree-shaking

export type { EChartsOption };

/** Design tokens resolved to concrete colours (canvas can't read CSS variables). */
export interface ChartColors {
  accent: string; ink: string; ink2: string; muted: string; grid: string;
  surface: string; surface2: string; border: string;
  pos: string; neg: string; mid: string;   // diverging performance poles + neutral midpoint
}

export function readColors(): ChartColors {
  const cs = getComputedStyle(document.documentElement);
  const v = (name: string) => cs.getPropertyValue(name).trim();
  return {
    accent: v("--accent"), ink: v("--ink"), ink2: v("--ink-2"), muted: v("--muted"),
    grid: v("--grid"), surface: v("--surface"), surface2: v("--surface-2"), border: v("--border"),
    pos: v("--pos"), neg: v("--neg"), mid: v("--mid"),
  };
}

/** Shared recessive tooltip / axis styling. */
export function tooltipStyle(c: ChartColors) {
  return {
    backgroundColor: c.surface2, borderColor: c.border, borderWidth: 1,
    textStyle: { color: c.ink, fontSize: 11 }, extraCssText: "box-shadow:none;border-radius:6px;",
    axisPointer: {
      type: "cross" as const,
      lineStyle: { color: c.muted, width: 1, type: "dashed" as const },
      crossStyle: { color: c.muted, width: 1, type: "dashed" as const },
      label: { backgroundColor: c.surface2, color: c.ink, borderColor: c.border, borderWidth: 1, fontSize: 10 },
    },
  };
}

export function axisStyle(c: ChartColors) {
  return {
    axisLine: { lineStyle: { color: c.grid } },
    axisTick: { show: false },
    axisLabel: { color: c.muted, fontSize: 10 },
    splitLine: { lineStyle: { color: c.grid, width: 1, opacity: 0.6 } },
  };
}
