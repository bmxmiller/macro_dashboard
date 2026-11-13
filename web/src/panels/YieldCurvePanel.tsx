import { useCallback } from "react";
import { axisStyle, tooltipStyle, type ChartColors, type EChartsOption } from "../components/chartTheme";
import { LazyEChart } from "../components/LazyEChart";
import { ExternalIcon } from "../components/Icons";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { fmtDate, signed } from "../lib/format";
import { useStale } from "../lib/stale";
import type { CurvePoint, Spread, YieldCurve } from "../types";

const pct = (v: unknown) => (typeof v === "number" ? `${v.toFixed(2)}%` : "–");

/** Treasury curve now vs 1M and 1Y ago, plus 2s10s / 3m10y spread tiles. */
export function YieldCurvePanel() {
  const { data, error } = useData<YieldCurve>("yield_curve");
  const stale = useStale("yield_curve");

  return (
    <Panel id="yield_curve" title="US Treasury Yield Curve"
      subtitle={data?.asof ? `As of ${fmtDate(data.asof, { month: "short", day: "numeric", year: "numeric" })}` : undefined}
      about={data?.about} sourceUrl={data?.source_url} stale={stale}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && (
        <div className="flex flex-col h-full min-h-0">
          <CurveChart points={data.points} />
          <div className="grid grid-cols-2 gap-1.5 px-2 pb-2 shrink-0">
            {data.spreads.map((s) => <SpreadTile key={s.series} spread={s} />)}
          </div>
        </div>
      )}
    </Panel>
  );
}

function CurveChart({ points }: { points: CurvePoint[] }) {
  const build = useCallback((c: ChartColors): EChartsOption => {
    const line = (name: string, key: "now" | "m1" | "y1", color: string, width: number, type: "solid" | "dashed" | "dotted") => ({
      type: "line" as const, name, data: points.map((p) => p[key]),
      showSymbol: key === "now", symbol: "circle", symbolSize: key === "now" ? 6 : 4,
      lineStyle: { color, width, type }, itemStyle: { color },
      z: key === "now" ? 3 : 2, emphasis: { disabled: true },
    });
    const ax = axisStyle(c);
    return {
      animation: false,
      grid: { left: 6, right: 12, top: 30, bottom: 4, containLabel: true },
      legend: {
        top: 2, right: 8, itemWidth: 18, itemHeight: 8, itemGap: 10,
        textStyle: { color: c.ink2, fontSize: 10 }, inactiveColor: c.grid,
      },
      tooltip: { trigger: "axis", ...tooltipStyle(c), valueFormatter: pct },
      xAxis: { type: "category", data: points.map((p) => p.label), boundaryGap: false, ...ax, splitLine: { show: false } },
      yAxis: { type: "value", scale: true, ...ax, axisLabel: { ...ax.axisLabel, formatter: (v: number) => `${v.toFixed(1)}%` } },
      series: [
        line("1Y ago", "y1", c.muted, 1.25, "dotted"),
        line("1M ago", "m1", c.ink2, 1.25, "dashed"),
        line("Now", "now", c.accent, 2, "solid"),
      ],
    };
  }, [points]);

  const now = points.map((p) => `${p.label} ${pct(p.now)}`).join(", ");
  return <LazyEChart build={build} className="flex-1 min-h-[200px] w-full" ariaLabel={`Yield curve now: ${now}`} />;
}

function SpreadTile({ spread: s }: { spread: Spread }) {
  const bp = s.value * 100;
  const d1m = s.m1 != null ? (s.value - s.m1) * 100 : null;
  const inverted = s.value < 0;
  return (
    <a href={s.data_url} target="_blank" rel="noopener noreferrer"
      className="group block rounded border px-2 py-1.5 hover:bg-[var(--surface-2)]"
      style={{ borderColor: inverted ? "var(--neg)" : "var(--border)", color: "var(--ink)" }}
      aria-label={`${s.label} spread ${signed(bp, 0, " bp")}${inverted ? ", inverted" : ""}, ${signed(d1m, 0, " bp")} versus 1 month ago`}>
      <div className="flex items-center gap-1.5">
        <span className="text-[10px] font-bold uppercase tracking-wide" style={{ color: "var(--ink-2)" }}>{s.label}</span>
        {inverted && (
          <span className="text-[8.5px] font-extrabold uppercase px-1 rounded-sm"
            style={{ background: "var(--neg)", color: "var(--surface)" }}>Inverted</span>
        )}
        <span className="ml-auto opacity-0 group-hover:opacity-100" style={{ color: "var(--muted)" }}><ExternalIcon /></span>
      </div>
      <div className="num text-[16px] font-bold leading-tight">{signed(bp, 0, " bp")}</div>
      <div className="num text-[10px]" style={{ color: "var(--muted)" }}>{signed(d1m, 0, " bp")} vs 1M</div>
    </a>
  );
}
