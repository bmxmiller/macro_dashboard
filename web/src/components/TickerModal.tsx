import { useCallback, useEffect, useMemo, useRef } from "react";
import { createPortal } from "react-dom";
import { useData } from "../lib/data";
import { fmtDate, perfBg, signed } from "../lib/format";
import type { Period, SP500History, SP500Row } from "../types";
import { axisStyle, tooltipStyle, type ChartColors, type EChartsOption } from "./chartTheme";
import { CloseIcon, ExternalIcon } from "./Icons";
import { LazyEChart } from "./LazyEChart";

const PERIODS: Period[] = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y"];
const usd = (v: unknown) =>
  typeof v === "number" ? `$${v.toLocaleString("en-US", { minimumFractionDigits: 2, maximumFractionDigits: 2 })}` : "–";
const fmtCap = (bn: number) => (bn >= 1000 ? `$${(bn / 1000).toFixed(2)}T` : `$${bn.toFixed(bn >= 100 ? 0 : 1)}B`);

/** Detail card for one S&P 500 company: all period returns, a 1-year price line and the Yahoo link. */
export function TickerModal({ row, rank, share, asof, onClose }: {
  row: SP500Row; rank: number; share: number; asof: string; onClose: () => void;
}) {
  const closeBtn = useRef<HTMLButtonElement>(null);
  const { data: hist, error } = useData<SP500History>("sp500_hist");

  useEffect(() => {
    const prev = document.activeElement as HTMLElement | null;
    closeBtn.current?.focus();
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && onClose();
    document.addEventListener("keydown", onKey);
    return () => { document.removeEventListener("keydown", onKey); prev?.focus?.(); };
  }, [onClose]);

  const points = useMemo(() => {
    const closes = hist?.series[row.t];
    if (!hist || !closes) return [] as [string, number][];
    return hist.dates.flatMap((d, i) => (closes[i] == null ? [] : [[d, closes[i] as number] as [string, number]]));
  }, [hist, row.t]);

  const build = useCallback((c: ChartColors): EChartsOption => {
    const ax = axisStyle(c);
    return {
      animation: false,
      grid: { left: 8, right: 16, top: 12, bottom: 8, containLabel: true },
      tooltip: { trigger: "axis", ...tooltipStyle(c), valueFormatter: usd },
      xAxis: { type: "time", ...ax, splitLine: { show: false } },
      yAxis: {
        type: "value", scale: true, ...ax,
        axisLabel: { ...ax.axisLabel, formatter: (v: number) => `$${v.toLocaleString("en-US")}` },
      },
      series: [{
        type: "line", name: row.t, data: points, showSymbol: false,
        lineStyle: { color: c.accent, width: 1.75 }, itemStyle: { color: c.accent }, emphasis: { disabled: true },
      }],
    };
  }, [points, row.t]);

  const titleId = `ticker-${row.t}-title`;
  const first = points[0];
  const last = points[points.length - 1];
  const muted = { color: "var(--muted)" };
  return createPortal(
    <div className="fixed inset-0 z-50 flex items-center justify-center p-3"
      style={{ background: "color-mix(in oklab, var(--page) 70%, transparent)" }}
      onMouseDown={(e) => e.target === e.currentTarget && onClose()}>
      <div role="dialog" aria-modal="true" aria-labelledby={titleId}
        className="w-full max-w-[720px] max-h-[92vh] flex flex-col rounded-md border shadow-2xl overflow-hidden"
        style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
        <header className="flex items-center gap-2 px-3 py-2 shrink-0"
          style={{ background: "var(--accent)", color: "var(--accent-ink)" }}>
          <div className="min-w-0 flex-1">
            <h2 id={titleId} className="m-0 text-[12px] font-extrabold uppercase tracking-wider truncate">
              {row.name} <span className="opacity-75">{row.t}</span>
            </h2>
            <div className="text-[10px] font-semibold uppercase tracking-wide opacity-75 truncate num">
              {row.sector} · {fmtCap(row.cap)} · {usd(row.price)}
            </div>
          </div>
          <div className="header-actions">
            <button ref={closeBtn} type="button" className="icon-btn" aria-label="Close details" title="Close (Esc)"
              onClick={onClose}><CloseIcon /></button>
          </div>
        </header>
        <div className="flex-1 min-h-0 overflow-auto scroll-thin">
          <div className="grid grid-cols-4 gap-1.5 p-3">
            {PERIODS.map((p) => (
              <div key={p} className="rounded px-2 py-1.5 text-center border"
                style={{ background: perfBg(row.returns[p], p), borderColor: "var(--border)" }}>
                <div className="text-[9.5px] font-bold uppercase" style={{ color: "var(--ink-2)" }}>{p}</div>
                <div className="num text-[14px] font-bold" style={{ color: "var(--ink)" }}>{signed(row.returns[p], 1)}</div>
              </div>
            ))}
          </div>
          <p className="m-0 px-3 text-[11px]" style={{ color: "var(--ink-2)" }}>
            #{rank} by market cap among the companies shown · about {share.toFixed(1)}% of their combined market cap (not the official index weight) · price returns, as of {asof}
          </p>
          <div className="px-3 pt-2.5 text-[10px] font-bold uppercase tracking-wide" style={muted}>
            Price, last 12 months{first && last ? ` · ${usd(first[1])} → ${usd(last[1])}` : ""}
          </div>
          {error && <p className="m-0 p-3 text-[12px]" style={muted}>Price history unavailable: {error}</p>}
          {!hist && !error && <p className="m-0 p-3 text-[12px]" style={muted}>Loading…</p>}
          {hist && (points.length > 1
            ? <LazyEChart build={build} className="w-full h-[240px]"
                ariaLabel={`${row.name} price over the last 12 months, from ${usd(first[1])} to ${usd(last[1])} on ${fmtDate(last[0], { month: "short", day: "numeric", year: "numeric" })}`} />
            : <p className="m-0 p-3 text-[12px]" style={muted}>No price history for {row.t}.</p>)}
          <div className="px-3 py-2.5 border-t" style={{ borderColor: "var(--border)" }}>
            <a href={`https://finance.yahoo.com/quote/${encodeURIComponent(row.t)}`} target="_blank" rel="noopener noreferrer"
              className="inline-flex items-center gap-1 text-[12px] font-semibold hover:underline py-1" style={{ color: "var(--accent)" }}>
              View {row.t} on Yahoo Finance <ExternalIcon />
              <span className="sr-only"> (opens in a new tab)</span>
            </a>
          </div>
        </div>
      </div>
    </div>,
    document.body,
  );
}
