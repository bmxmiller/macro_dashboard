import { useEffect, useRef, type CSSProperties } from "react";
import * as echarts from "echarts/core";
import { LineChart } from "echarts/charts";
import {
  DataZoomComponent, GridComponent, LegendComponent, MarkAreaComponent, TooltipComponent,
} from "echarts/components";
import { CanvasRenderer } from "echarts/renderers";
import { readColors, type ChartColors, type EChartsOption } from "./chartTheme";
import { useSettings } from "../state/store";

echarts.use([LineChart, GridComponent, TooltipComponent, MarkAreaComponent, DataZoomComponent, LegendComponent, CanvasRenderer]);

/**
 * Thin ECharts wrapper. `build` receives the current theme colours and must be
 * memoised by the caller; the chart re-renders when it, the theme, palette or
 * accent change. Load it via <LazyEChart> so echarts stays in its own chunk.
 */
export default function EChart({ build, className = "", style, ariaLabel }: {
  build: (c: ChartColors) => EChartsOption; className?: string; style?: CSSProperties; ariaLabel: string;
}) {
  const el = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);
  const theme = useSettings((s) => s.theme);
  const palette = useSettings((s) => s.palette);
  const accent = useSettings((s) => s.accent);

  useEffect(() => {
    if (!el.current) return;
    const c = echarts.init(el.current, undefined, { renderer: "canvas" });
    chart.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(el.current);
    return () => { ro.disconnect(); c.dispose(); chart.current = null; };
  }, []);

  useEffect(() => {
    // App applies data-theme/--accent in its own effect, which runs after ours:
    // wait a frame so the CSS variables we read are the new ones.
    const id = requestAnimationFrame(() => {
      chart.current?.setOption(build(readColors()), { notMerge: true });
    });
    return () => cancelAnimationFrame(id);
  }, [build, theme, palette, accent]);

  return <div ref={el} role="img" aria-label={ariaLabel} className={className} style={style} />;
}
