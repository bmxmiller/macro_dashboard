import { useMemo, useState } from "react";
import { ExternalIcon, SortIcon } from "../components/Icons";
import { Panel, PanelMessage } from "../components/Panel";
import { RowHover, type HoverState } from "../components/RowHover";
import { useData } from "../lib/data";
import { fmtReturn, perfBg } from "../lib/format";
import { useSettings } from "../state/store";
import type { MarketRow, Markets, Meta } from "../types";

/**
 * Generic ranked-performance table (sectors, fixed income, commodities, FX…).
 * REFERENCE PATTERN for new panels: useData → <Panel> shell → rows.
 */
export function PerformancePanel({ panelId, showYield = false }: { panelId: string; showYield?: boolean }) {
  const { data, error } = useData<Markets>("markets");
  const { data: meta } = useData<Meta>("meta");
  const period = useSettings((s) => s.period);
  const [sorted, setSorted] = useState(true);
  const [hover, setHover] = useState<HoverState | null>(null);

  const panel = data?.panels[panelId];
  const groups = useMemo(() => {
    if (!panel) return [];
    if (!sorted) return panel.groups;
    const v = (r: MarketRow) => r.returns[period] ?? -Infinity;
    return panel.groups.map((g) => ({ ...g, rows: [...g.rows].sort((a, b) => v(b) - v(a)) }));
  }, [panel, sorted, period]);

  const stale = meta?.sections.markets?.ok === false ? meta.sections.markets.error ?? "update failed" : null;

  return (
    <Panel id={panelId} title={panel?.title ?? panelId} subtitle={`Total return · ${period}`}
      about={panel?.about} stale={stale}
      headerRight={
        <button type="button" className="icon-btn" data-no-export aria-pressed={sorted}
          title={sorted ? "Sorted by return (click for default order)" : "Default order (click to sort)"}
          onClick={() => setSorted((s) => !s)}><SortIcon /></button>
      }>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {groups.map((g) => (
        <div key={g.label}>
          <div className="group-label px-3 pt-2.5 pb-1 sticky top-0 z-[1]" style={{ background: "var(--surface)" }}>
            {g.label}
          </div>
          <table className="w-full border-collapse">
            <tbody>
              {g.rows.map((r) => (
                <tr key={r.ticker} className="border-t" style={{ borderColor: "var(--border)" }}
                  onMouseMove={(e) => setHover({ row: r, x: e.clientX, y: e.clientY })}
                  onMouseLeave={() => setHover(null)}>
                  <td className="pl-3 pr-1 py-[5px] whitespace-nowrap">
                    <a href={r.source_url} target="_blank" rel="noopener noreferrer"
                      className="group inline-flex items-center gap-1.5 font-semibold hover:underline" style={{ color: "var(--ink)" }}>
                      {r.name}
                      <span className="text-[9.5px] font-medium uppercase" style={{ color: "var(--muted)" }}>{r.tag}</span>
                      <span className="opacity-0 group-hover:opacity-100" style={{ color: "var(--muted)" }}><ExternalIcon /></span>
                    </a>
                  </td>
                  {showYield && (
                    <td className="px-1 text-right num whitespace-nowrap text-[10.5px]" style={{ color: "var(--ink-2)" }}>
                      {r.yield_ttm != null ? `${r.yield_ttm.toFixed(1)}%` : "–"}
                      <span style={{ color: "var(--muted)" }}> / {r.duration != null ? `${r.duration}y` : "–"}</span>
                    </td>
                  )}
                  <td className="w-[78px] pr-2 py-[3px]">
                    <div className="num text-right font-bold rounded-sm px-1.5 py-[2px]"
                      style={{ background: perfBg(r.returns[period], period, r.mode), color: "var(--ink)" }}>
                      {fmtReturn(r.returns[period], r.mode)}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ))}
      {showYield && data && (
        <div className="px-3 py-2 text-[10px]" style={{ color: "var(--muted)" }}>
          Yield = trailing-12-month distributions ÷ price · duration ≈ effective (approx.)
        </div>
      )}
      <RowHover hover={hover} periods={data?.periods ?? []} />
    </Panel>
  );
}
