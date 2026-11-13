import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { fmtDate, fmtValue } from "../lib/format";
import type { Metric } from "../types";
import { AboutCard } from "./AboutCard";
import { axisStyle, tooltipStyle, type ChartColors, type EChartsOption } from "./chartTheme";
import { LazyEChart } from "./LazyEChart";
import { CloseIcon } from "./Icons";
import { MetricStats } from "./MetricStats";

const RANGES = [["1Y", 1], ["5Y", 5], ["10Y", 10], ["Max", null]] as const;
type Range = (typeof RANGES)[number][0];

function cutoff(last: string, years: number | null): string {
  if (years == null) return "";
  const d = new Date(`${last}T00:00:00Z`);
  d.setUTCFullYear(d.getUTCFullYear() - years);
  return d.toISOString().slice(0, 10);
}

/** Full-history chart for one metric, with NBER recession shading and range buttons. */
export function HistoryModal({ metric, recessions, onClose }: {
  metric: Metric; recessions: [string, string][]; onClose: () => void;
}) {
  const [range, setRange] = useState<Range>("10Y");
  const closeBtn = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus?.(); };
  }, [onClose]);

  const data = useMemo(() => {
    const h = metric.history;
    if (!h.length) return h;
    const from = cutoff(h[h.length - 1][0], RANGES.find((r) => r[0] === range)![1]);
    return h.filter(([d]) => d >= from);
  }, [metric.history, range]);

  const build = useCallback((c: ChartColors): EChartsOption => {
    const from = data[0]?.[0] ?? "";
    const areas = recessions
      .filter(([, end]) => end >= from)
      .map(([s, e]) => [{ xAxis: s < from ? from : s }, { xAxis: e }]);
    const fmt = (v: number) => fmtValue(v, metric.decimals, metric.units);
    return {
      animation: false,
      grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
      tooltip: {
        trigger: "axis", ...tooltipStyle(c),
        valueFormatter: (v) => (typeof v === "number" ? fmt(v) : "–"),
      },
      dataZoom: [{ type: "inside", throttle: 30 }],
      xAxis: { type: "time", ...axisStyle(c), splitLine: { show: false } },
      yAxis: {
        type: "value", scale: true, ...axisStyle(c),
        axisLabel: { ...axisStyle(c).axisLabel, formatter: (v: number) => fmt(v) },
      },
      series: [{
        type: "line", name: metric.name, data, showSymbol: false, symbolSize: 8,
        lineStyle: { width: 2, color: c.accent }, itemStyle: { color: c.accent },
        emphasis: { disabled: true },
        markArea: {
          silent: true, itemStyle: { color: c.muted, opacity: 0.16 },
          data: areas as never,
        },
      }],
    };
  }, [data, recessions, metric]);

  const titleId = `hist-${metric.id}-title`;

  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3"
      style={{ background: "color-mix(in oklab, var(--page) 70%, transparent)" }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby={titleId}
        className="w-full max-w-[960px] max-h-[92vh] flex flex-col rounded-md border shadow-2xl overflow-hidden"
        style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
        <header className="flex items-center gap-2 px-3 py-2 shrink-0"
          style={{ background: "var(--accent)", color: "var(--accent-ink)" }}>
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="m-0 text-[12px] font-extrabold uppercase tracking-wider truncate">{metric.name}</h2>
            <div className="text-[10px] font-semibold uppercase tracking-wide opacity-75 truncate num">
              {fmtValue(metric.value, metric.decimals, metric.units)} · {metric.period_label ?? "–"}
              {metric.history.length > 0 && ` · history since ${fmtDate(metric.history[0][0], { year: "numeric", month: "short" })}`}
            </div>
          </div>
          <div className="header-actions">
            <button ref={closeBtn} type="button" className="icon-btn" aria-label="Close history" title="Close (Esc)"
              onClick={onClose}><CloseIcon /></button>
          </div>
        </header>
        <div className="flex-1 min-h-0 overflow-auto scroll-thin">
          <div className="flex items-center gap-1 px-3 pt-2.5" role="group" aria-label="Chart range">
            {RANGES.map(([r]) => (
              <button key={r} type="button" aria-pressed={range === r} onClick={() => setRange(r)}
                className="px-2 py-0.5 rounded text-[10.5px] font-bold border"
                style={range === r
                  ? { background: "var(--accent)", color: "var(--accent-ink)", borderColor: "var(--accent)" }
                  : { color: "var(--ink-2)", borderColor: "var(--border)" }}>
                {r}
              </button>
            ))}
            <span className="ml-auto text-[10px] flex items-center gap-1.5" style={{ color: "var(--muted)" }}>
              <span aria-hidden className="inline-block w-3 h-2.5 rounded-sm"
                style={{ background: "color-mix(in oklab, var(--muted) 30%, transparent)" }} />
              NBER recession · scroll to zoom
            </span>
          </div>
          <LazyEChart build={build} className="w-full h-[320px]"
            ariaLabel={`${metric.name} history chart, ${range} range, latest ${fmtValue(metric.value, metric.decimals, metric.units)}`} />
          <div className="border-t" style={{ borderColor: "var(--border)" }}>
            <AboutCard title={`About ${metric.name}`} about={metric.about} sourceUrl={metric.source_url}
              extra={<MetricStats metric={metric} />} />
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
