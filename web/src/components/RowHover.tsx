import { createPortal } from "react-dom";
import { fmtPrice, fmtReturn, perfBg } from "../lib/format";
import type { MarketRow, Period } from "../types";
import { Sparkline } from "./Sparkline";

export interface HoverState { row: MarketRow; x: number; y: number }

/** Hover card for a market row: every period at once, price, sparkline, source. */
export function RowHover({ hover, periods }: { hover: HoverState | null; periods: Period[] }) {
  if (!hover) return null;
  const { row, x, y } = hover;
  const w = 250;
  const left = x + 16 + w > window.innerWidth ? x - w - 16 : x + 16;
  const top = Math.min(y - 10, window.innerHeight - 230);
  return createPortal(
    <div className="fixed z-50 pointer-events-none rounded-md border shadow-2xl p-2.5 text-[11px]"
      style={{ left, top, width: w, background: "var(--surface-2)", borderColor: "var(--border)" }}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="font-semibold text-[12px]" style={{ color: "var(--ink)" }}>{row.name}</span>
        <span className="mono" style={{ color: "var(--muted)" }}>{row.ticker}</span>
      </div>
      <div className="flex items-center justify-between mt-1 mb-2">
        <span className="num" style={{ color: "var(--ink-2)" }}>
          {fmtPrice(row.price)} {row.units && <span style={{ color: "var(--muted)" }}>{row.units}</span>}
        </span>
        <Sparkline data={row.spark} width={100} height={24} />
      </div>
      <div className="grid grid-cols-4 gap-1">
        {periods.map((p) => (
          <div key={p} className="rounded px-1 py-0.5 text-center" style={{ background: perfBg(row.returns[p], p, row.mode) }}>
            <div className="text-[9px] font-semibold" style={{ color: "var(--muted)" }}>{p}</div>
            <div className="num font-semibold" style={{ color: "var(--ink)" }}>{fmtReturn(row.returns[p], row.mode)}</div>
          </div>
        ))}
      </div>
      {row.yield_ttm != null && (
        <div className="mt-2 flex justify-between" style={{ color: "var(--ink-2)" }}>
          <span>TTM yield <b className="num">{row.yield_ttm.toFixed(1)}%</b></span>
          {row.duration != null && <span>Eff. duration ≈ <b className="num">{row.duration}y</b></span>}
        </div>
      )}
      <div className="mt-1.5 text-[10px]" style={{ color: "var(--muted)" }}>
        As of {row.asof ?? "–"} · click name for source
      </div>
    </div>,
    document.body,
  );
}
