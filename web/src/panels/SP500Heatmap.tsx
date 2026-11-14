import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { tooltipStyle, type ChartColors, type EChartsOption } from "../components/chartTheme";
import { LazyEChart } from "../components/LazyEChart";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { perfColor, signed } from "../lib/format";
import { useStale } from "../lib/stale";
import { useSettings } from "../state/store";
import type { Period, SP500, SP500Row } from "../types";

const TOOLTIP_PERIODS: Period[] = ["1D", "1W", "1M", "3M", "YTD", "1Y"];
const quoteUrl = (t: string) => `https://finance.yahoo.com/quote/${encodeURIComponent(t)}`;
const esc = (s: string) => s.replace(/[&<>"']/g, (ch) => `&#${ch.charCodeAt(0)};`);
const fmtCap = (bn: number) => (bn >= 1000 ? `$${(bn / 1000).toFixed(2)}T` : `$${bn.toFixed(bn >= 100 ? 0 : 1)}B`);

interface Leaf { name: string; value: number; t: string; row: SP500Row }

/** S&P 500 treemap: rectangle area = market cap, grouped by GICS sector, colour = price return. */
export function SP500Heatmap() {
  const { data, error } = useData<SP500>("sp500");
  const stale = useStale("sp500");
  const period = useSettings((s) => s.period);

  // Largest daily-or-period movers among the 100 biggest companies: a text readout so
  // the map is not colour-only.
  const movers = useMemo(() => {
    if (!data) return null;
    const top = data.rows.slice(0, 100).filter((r) => r.returns[period] != null);
    const sorted = [...top].sort((a, b) => (b.returns[period] as number) - (a.returns[period] as number));
    return { up: sorted.slice(0, 3), down: sorted.slice(-3).reverse() };
  }, [data, period]);

  return (
    <Panel id="sp500_heatmap" title="S&P 500 Heat Map"
      subtitle={`Price return · ${period} · size = market cap`}
      about={data?.about} sourceUrl={data?.source_url} stale={stale}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && (
        <div className="flex flex-col h-full min-h-0">
          <Treemap data={data} period={period} />
          {movers && (
            <div className="px-3 py-1.5 text-[10.5px] flex flex-wrap gap-x-4 gap-y-0.5 shrink-0 border-t"
              style={{ color: "var(--ink-2)", borderColor: "var(--border)" }}>
              <Movers label="Leaders (top 100 by cap)" rows={movers.up} period={period} />
              <Movers label="Laggards" rows={movers.down} period={period} />
              <span className="ml-auto" style={{ color: "var(--muted)" }}>
                {data.rows.length} companies · as of {data.asof}
              </span>
            </div>
          )}
        </div>
      )}
    </Panel>
  );
}

function Movers({ label, rows, period }: { label: string; rows: SP500Row[]; period: Period }) {
  return (
    <span>
      <span style={{ color: "var(--muted)" }}>{label}: </span>
      {rows.map((r, i) => (
        <span key={r.t}>
          {i > 0 && ", "}
          <a href={quoteUrl(r.t)} target="_blank" rel="noopener noreferrer" className="font-semibold hover:underline"
            style={{ color: "var(--ink)" }}>{r.t}</a>{" "}
          <span className="num">{signed(r.returns[period], 1)}</span>
        </span>
      ))}
    </span>
  );
}

/** Rough glyph width (px) of the 10px bold labels, used to decide whether a label fits its rectangle whole. */
const CHAR_PX = 6.4;
const PAD_PX = 12;

function Treemap({ data, period }: { data: SP500; period: Period }) {
  // Measure the container so a label is only drawn when it fits whole (a clipped "+1." would misread).
  const box = useRef<HTMLDivElement>(null);
  const [area, setArea] = useState(0);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    const ro = new ResizeObserver(() => setArea(Math.round((el.clientWidth * el.clientHeight) / 1000) * 1000));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  const total = useMemo(() => data.rows.reduce((a, r) => a + r.cap, 0), [data]);

  const build = useCallback((c: ChartColors): EChartsOption => {
    const bySector = new Map<string, Leaf[]>();
    for (const r of data.rows) {
      const leaf: Leaf = { name: r.t, value: r.cap, t: r.t, row: r };
      bySector.set(r.sector, [...(bySector.get(r.sector) ?? []), leaf]);
    }
    const tree = [...bySector.entries()]
      .map(([sector, leaves]) => ({
        name: sector,
        value: leaves.reduce((a, l) => a + l.value, 0),
        children: leaves.map((l) => ({ ...l, itemStyle: { color: perfColor(l.row.returns[period], period, c) } })),
      }))
      .sort((a, b) => b.value - a.value);

    return {
      animation: false,
      tooltip: {
        ...tooltipStyle(c), confine: true,
        formatter: (p: unknown) => {
          const d = (p as { data: Partial<Leaf> & { name: string; value: number; children?: unknown[] } }).data;
          if (!d.row) return `<b>${esc(d.name)}</b><br/>${d.children?.length ?? 0} companies · ${fmtCap(d.value)}`;
          const r = d.row;
          const cells = TOOLTIP_PERIODS.map((k) => `${k} <b>${signed(r.returns[k], 1)}</b>`).join(" &nbsp; ");
          return `<b>${esc(r.name)}</b> <span style="opacity:.7">${esc(r.t)}</span><br/>`
            + `${esc(r.sector)} · ${fmtCap(r.cap)} · $${r.price.toLocaleString("en-US")}<br/>${cells}`;
        },
      },
      series: [{
        type: "treemap", roam: false, nodeClick: false, breadcrumb: { show: false },
        left: 0, right: 0, top: 0, bottom: 0, squareRatio: 1,
        visibleMin: 2, childrenVisibleMin: 2,
        label: {
          show: true, color: c.ink, fontSize: 10, fontWeight: 600, overflow: "truncate", ellipsis: "…",
          formatter: (p: unknown) => {
            const d = (p as { data: Partial<Leaf> }).data;
            if (!d.row) return "";
            const w = Math.sqrt((d.row.cap / total) * area * 0.55);   // approx. side of this (near-square) rectangle, px
            const pct = signed(d.row.returns[period], 1);
            const need = Math.max(d.row.t.length, pct.length) * CHAR_PX + PAD_PX;
            if (w >= need && w >= 30) return `${d.row.t}\n${pct}`;
            return w >= d.row.t.length * CHAR_PX + PAD_PX ? d.row.t : "";
          },
        },
        upperLabel: { show: true, height: 16, color: c.ink, fontSize: 10, fontWeight: 600, padding: [0, 0, 0, 3], formatter: "{b}" },
        levels: [   // [0] is ECharts' invisible root, [1] the sectors, [2] the companies
          { itemStyle: { borderWidth: 0, gapWidth: 0 }, upperLabel: { show: false } },
          { itemStyle: { color: c.surface2, borderColor: c.surface2, borderWidth: 0, gapWidth: 3 } },
          { itemStyle: { borderWidth: 0, gapWidth: 1 }, upperLabel: { show: false } },
        ],
        emphasis: { disabled: false, itemStyle: { borderColor: c.ink, borderWidth: 1 } },
        data: tree,
      }],
    } as EChartsOption;
  }, [data, period, area, total]);

  const onClick = useCallback((d: unknown) => {
    const t = (d as { t?: string } | undefined)?.t;
    if (t) window.open(quoteUrl(t), "_blank", "noopener,noreferrer");
  }, []);

  return (
    <div ref={box} className="relative flex-1 min-h-80 w-full">
      <LazyEChart build={build} onClick={onClick} className="absolute inset-0"
        ariaLabel={`S&P 500 heat map: ${data.rows.length} companies sized by market cap, coloured by ${period} price return`} />
    </div>
  );
}
