import { useCallback, useState } from "react";
import { axisStyle, tooltipStyle, type ChartColors, type EChartsOption } from "../components/chartTheme";
import { LazyEChart } from "../components/LazyEChart";
import { ExternalIcon } from "../components/Icons";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { fmtDate, signed } from "../lib/format";
import { useStale } from "../lib/stale";
import type { CurvePoint, Spread, YieldCurve } from "../types";

const pct = (v: unknown) => (typeof v === "number" ? `${v.toFixed(2)}%` : "–");

/** Treasury curve now vs 1M and 1Y ago, plus 2s10s / 3m10y tiles that open a spread history with inversions shaded. */
export function YieldCurvePanel() {
  const { data, error } = useData<YieldCurve>("yield_curve");
  const stale = useStale("yield_curve");
  const [view, setView] = useState<string | null>(null);   // null = the curve, else a spread's FRED series id
  const spread = data?.spreads.find((s) => s.series === view) ?? null;

  return (
    <Panel id="yield_curve" title="US Treasury Yield Curve"
      subtitle={data?.asof ? `As of ${fmtDate(data.asof, { month: "short", day: "numeric", year: "numeric" })}` : undefined}
      about={data?.about} sourceUrl={data?.source_url} stale={stale} updatedSection="yield_curve">
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && (
        <div className="flex flex-col h-full min-h-0">
          {spread ? <SpreadChart spread={spread} /> : <CurveChart points={data.points} />}
          <div className="flex items-center gap-1 px-2 pt-1 shrink-0" role="group" aria-label="Chart view">
            {[["Curve", null], ...data.spreads.map((s) => [`${s.label} history`, s.series] as const)].map(([label, key]) => (
              <button key={label} type="button" aria-pressed={view === key} onClick={() => setView(key)}
                className="px-2 py-0.5 rounded text-[10px] font-bold border"
                style={view === key
                  ? { background: "var(--accent)", color: "var(--accent-ink)", borderColor: "var(--accent)" }
                  : { color: "var(--ink-2)", borderColor: "var(--border)" }}>{label}</button>
            ))}
          </div>
          <div className="grid grid-cols-2 gap-1.5 p-2 shrink-0">
            {data.spreads.map((s) => <SpreadTile key={s.series} spread={s} active={view === s.series}
              onSelect={() => setView(view === s.series ? null : s.series)} />)}
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

/** [start, end] date pairs where the spread is below zero (end = first non-negative point, or the last point). */
export function inversionRuns(h: [string, number][]): [string, string][] {
  const runs: [string, string][] = [];
  let start: string | null = null;
  for (let i = 0; i < h.length; i++) {
    const neg = h[i][1] < 0;
    if (neg && start == null) start = h[i][0];
    if (!neg && start != null) { runs.push([start, h[i][0]]); start = null; }
  }
  if (start != null) runs.push([start, h[h.length - 1][0]]);
  return runs;
}

function SpreadChart({ spread: s }: { spread: Spread }) {
  const bp = (v: unknown) => (typeof v === "number" ? signed(v, 0, " bp") : "–");
  const build = useCallback((c: ChartColors): EChartsOption => {
    const data = s.history.map(([d, v]) => [d, Math.round(v * 100)] as [string, number]);
    const ax = axisStyle(c);
    return {
      animation: false,
      grid: { left: 6, right: 14, top: 14, bottom: 4, containLabel: true },
      tooltip: { trigger: "axis", ...tooltipStyle(c), valueFormatter: bp },
      xAxis: { type: "time", ...ax, splitLine: { show: false } },
      yAxis: { type: "value", scale: true, ...ax, axisLabel: { ...ax.axisLabel, formatter: (v: number) => signed(v, 0, "") } },
      series: [{
        type: "line", name: s.label, data, showSymbol: false, lineStyle: { color: c.accent, width: 1.75 },
        itemStyle: { color: c.accent }, emphasis: { disabled: true },
        markLine: { silent: true, symbol: "none", label: { show: false }, lineStyle: { color: c.ink2, width: 1, type: "solid" }, data: [{ yAxis: 0 }] },
        markArea: {
          silent: true, itemStyle: { color: c.neg, opacity: 0.16 },
          data: inversionRuns(s.history).map(([a, b]) => [{ xAxis: a }, { xAxis: b }]),
        },
      }],
    };
  }, [s]);

  const last = s.history[s.history.length - 1];
  return (
    <div className="flex-1 min-h-[200px] flex flex-col">
      <LazyEChart build={build} className="flex-1 min-h-[180px] w-full"
        ariaLabel={`${s.label} spread history in basis points, latest ${bp(s.value * 100)}${last ? ` on ${last[0]}` : ""}; shaded where inverted`} />
      <div className="px-3 pb-0.5 text-[10px] flex items-center gap-1.5" style={{ color: "var(--muted)" }}>
        <span aria-hidden className="inline-block w-3 h-2.5 rounded-sm"
          style={{ background: "color-mix(in oklab, var(--neg) 30%, transparent)" }} />
        Shaded = inverted (below 0 bp) · basis points · weekly
      </div>
    </div>
  );
}

function SpreadTile({ spread: s, active, onSelect }: { spread: Spread; active: boolean; onSelect: () => void }) {
  const bp = s.value * 100;
  const d1m = s.m1 != null ? (s.value - s.m1) * 100 : null;
  const inverted = s.value < 0;
  return (
    <div className="group relative rounded border hover:bg-[var(--surface-2)]"
      style={{ borderColor: inverted ? "var(--neg)" : active ? "var(--accent)" : "var(--border)", color: "var(--ink)" }}>
      <button type="button" onClick={onSelect} aria-pressed={active} className="block w-full text-left px-2 py-1.5"
        aria-label={`${s.label} spread ${signed(bp, 0, " bp")}${inverted ? ", inverted" : ""}, ${signed(d1m, 0, " bp")} versus 1 month ago. Show history`}>
        <div className="flex items-center gap-1.5">
          <span className="text-[10px] font-bold uppercase tracking-wide" style={{ color: "var(--ink-2)" }}>{s.label}</span>
          {inverted && (
            <span className="text-[8.5px] font-extrabold uppercase px-1 rounded-sm"
              style={{ background: "var(--neg)", color: "var(--surface)" }}>Inverted</span>
          )}
        </div>
        <div className="num text-[16px] font-bold leading-tight">{signed(bp, 0, " bp")}</div>
        <div className="num text-[10px]" style={{ color: "var(--muted)" }}>{signed(d1m, 0, " bp")} vs 1M</div>
      </button>
      <a href={s.data_url} target="_blank" rel="noopener noreferrer" aria-label={`${s.label} data on FRED (opens in a new tab)`}
        className="absolute top-1 right-1 p-1 opacity-60 hover:opacity-100" style={{ color: "var(--muted)" }}><ExternalIcon /></a>
    </div>
  );
}
