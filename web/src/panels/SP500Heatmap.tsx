import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { tooltipStyle, type ChartColors, type EChartsOption } from "../components/chartTheme";
import { LazyEChart } from "../components/LazyEChart";
import { TickerModal } from "../components/TickerModal";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { perfBg, perfColor, perfScale, signed } from "../lib/format";
import { useStale } from "../lib/stale";
import { useSettings, type HeatSize } from "../state/store";
import type { Period, SP500, SP500Row } from "../types";

const TOOLTIP_PERIODS: Period[] = ["1D", "1W", "1M", "3M", "YTD", "1Y"];
const SIZE_NAME: Record<HeatSize, string> = { sqrt: "√ market cap", cap: "market cap", equal: "equal weight" };
const coarse = () => window.matchMedia("(pointer: coarse)").matches;
const esc = (s: string) => s.replace(/[&<>"']/g, (ch) => `&#${ch.charCodeAt(0)};`);
const fmtCap = (bn: number) => (bn >= 1000 ? `$${(bn / 1000).toFixed(2)}T` : `$${bn.toFixed(bn >= 100 ? 0 : 1)}B`);

interface Leaf { name: string; value: number; t: string; row: SP500Row }

/** S&P 500 treemap: rectangle area = market cap (or equal weight), grouped by GICS sector, colour = price return. */
export function SP500Heatmap() {
  const { data, error } = useData<SP500>("sp500");
  const stale = useStale("sp500");
  const period = useSettings((s) => s.period);
  const size = useSettings((s) => s.heatSize);
  const setSize = useSettings((s) => s.setHeatSize);
  const [picked, setPicked] = useState<string | null>(null);   // ticker whose detail card is open
  const close = useCallback(() => setPicked(null), []);
  const detail = useMemo(() => {
    if (!data || !picked) return null;
    const i = data.rows.findIndex((r) => r.t === picked);
    if (i < 0) return null;
    const total = data.rows.reduce((a, r) => a + r.cap, 0);
    return { row: data.rows[i], rank: i + 1, share: (data.rows[i].cap / total) * 100 };
  }, [data, picked]);

  // Biggest movers among the 100 largest companies: a text readout so the map is not colour-only.
  const movers = useMemo(() => {
    if (!data) return null;
    const top = data.rows.slice(0, 100).filter((r) => r.returns[period] != null);
    const sorted = [...top].sort((a, b) => (b.returns[period] as number) - (a.returns[period] as number));
    return { up: sorted.slice(0, 3), down: sorted.slice(-3).reverse() };
  }, [data, period]);

  return (
    <Panel id="sp500_heatmap" title="S&P 500 Heat Map"
      subtitle={`Price return · ${period} · size = ${SIZE_NAME[size]}`}
      about={data?.about} sourceUrl={data?.source_url} stale={stale} updatedSection="sp500"
      headerRight={<SizeToggle size={size} onChange={setSize} />}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && (
        <div className="flex flex-col h-full min-h-0">
          <Treemap data={data} period={period} size={size} onPick={setPicked} />
          <DataTable rows={data.rows} asof={data.asof} />
          <div className="px-3 py-1 text-[11px] shrink-0 border-t flex flex-col gap-0.5"
            style={{ color: "var(--ink-2)", borderColor: "var(--border)" }}>
            {movers && (
              <div className="flex flex-wrap items-center gap-x-4">
                <span style={{ color: "var(--muted)" }}>Top-100 movers · {period}:</span>
                <Movers label="Leaders" rows={movers.up} period={period} onPick={setPicked} />
                <Movers label="Laggards" rows={movers.down} period={period} onPick={setPicked} />
              </div>
            )}
            <div className="flex flex-wrap items-center gap-x-4 gap-y-0.5" style={{ color: "var(--muted)" }}>
              <Legend period={period} />
              <span className="sm:ml-auto">
                {data.rows.length} companies · <time dateTime={data.asof}>as of {data.asof}</time>
              </span>
            </div>
          </div>
        </div>
      )}
      {detail && <TickerModal row={detail.row} rank={detail.rank} share={detail.share} asof={data!.asof} onClose={close} />}
    </Panel>
  );
}

/** Market cap | Equal weight, styled for the accent header bar. */
function SizeToggle({ size, onChange }: { size: HeatSize; onChange: (s: HeatSize) => void }) {
  const opts: [HeatSize, string][] = [["sqrt", "Balanced"], ["cap", "Mkt cap"], ["equal", "Equal wt"]];
  return (
    <div role="group" aria-label="Rectangle size" data-no-export
      className="flex rounded border overflow-hidden text-[9.5px] font-bold" style={{ borderColor: "currentColor" }}>
      {opts.map(([k, label]) => (
        <button key={k} type="button" aria-pressed={size === k} onClick={() => onChange(k)} className="px-1.5 py-[2px]"
          style={size === k ? { background: "var(--accent-ink)", color: "var(--accent)" } : { opacity: 0.8 }}>{label}</button>
      ))}
    </div>
  );
}

function Movers({ label, rows, period, onPick }: { label: string; rows: SP500Row[]; period: Period; onPick: (t: string) => void }) {
  return (
    <span>
      <span style={{ color: "var(--muted)" }}>{label}: </span>
      {rows.map((r, i) => (
        <span key={r.t}>
          {i > 0 && ", "}
          <button type="button" onClick={() => onPick(r.t)} aria-label={`${r.t}: show details`}
            className="inline-block py-1.5 font-semibold hover:underline" style={{ color: "var(--ink)" }}>{r.t}</button>{" "}
          <span className="num">{signed(r.returns[period], 1)}</span>
        </span>
      ))}
    </span>
  );
}

/** Colour key: the scale saturates at ±X% for the selected period. */
function Legend({ period }: { period: Period }) {
  const x = perfScale(period);
  const bg = `linear-gradient(to right, ${perfBg(-x, period)}, ${perfBg(-x / 3, period)}, var(--mid), ${perfBg(x / 3, period)}, ${perfBg(x, period)})`;
  return (
    <span className="inline-flex items-center gap-1.5" aria-hidden="true">
      <span className="num">{signed(-x, 0)}</span>
      <span className="inline-block h-2 w-24 rounded-sm border" style={{ background: bg, borderColor: "var(--border)" }} />
      <span className="num">{signed(x, 0)}</span>
      <span>or beyond ({period})</span>
    </span>
  );
}

/** Screen-reader alternative to the canvas: every company with its market cap and returns. */
function DataTable({ rows, asof }: { rows: SP500Row[]; asof: string }) {
  return (
    <div className="sr-only">   {/* wrapper, not the table: a table ignores overflow:hidden and widens the page */}
    <table>
      <caption>S&amp;P 500 companies by market cap, price returns in percent, as of {asof}</caption>
      <thead>
        <tr>
          <th scope="col">Ticker</th><th scope="col">Company</th><th scope="col">Sector</th>
          <th scope="col">Market cap ($bn)</th>
          {TOOLTIP_PERIODS.map((p) => <th scope="col" key={p}>{p}</th>)}
        </tr>
      </thead>
      <tbody>
        {rows.map((r) => (
          <tr key={r.t}>
            <th scope="row">{r.t}</th><td>{r.name}</td><td>{r.sector}</td><td>{r.cap}</td>
            {TOOLTIP_PERIODS.map((p) => <td key={p}>{signed(r.returns[p], 1)}</td>)}
          </tr>
        ))}
      </tbody>
    </table>
    </div>
  );
}

/** Rough glyph width (px) of the 10px bold labels, with margin, used to decide whether a label fits whole. */
const CHAR_PX = 7.2;
const PAD_PX = 12;

function Treemap({ data, period, size, onPick }: { data: SP500; period: Period; size: HeatSize; onPick: (t: string) => void }) {
  // Measure the container so a label is only drawn when it fits whole (a clipped "+1." would misread).
  const box = useRef<HTMLDivElement>(null);
  const [area, setArea] = useState(0);
  useEffect(() => {
    const el = box.current;
    if (!el) return;
    let timer: number | undefined;
    const measure = () => setArea(Math.round((el.clientWidth * el.clientHeight) / 1000) * 1000);
    const ro = new ResizeObserver(() => { window.clearTimeout(timer); timer = window.setTimeout(measure, 120); });
    ro.observe(el);
    measure();
    return () => { window.clearTimeout(timer); ro.disconnect(); };
  }, []);
  const weight = useCallback((r: SP500Row) => size === "cap" ? r.cap : size === "sqrt" ? Math.sqrt(r.cap) : 1, [size]);
  const total = useMemo(() => data.rows.reduce((a, r) => a + weight(r), 0), [data, weight]);

  const build = useCallback((c: ChartColors): EChartsOption => {
    const bySector = new Map<string, Leaf[]>();
    for (const r of data.rows) {
      const leaf: Leaf = { name: r.t, value: weight(r), t: r.t, row: r };
      bySector.set(r.sector, [...(bySector.get(r.sector) ?? []), leaf]);
    }
    const tree = [...bySector.entries()]
      .map(([sector, leaves]) => ({
        name: sector,
        cap: leaves.reduce((a, l) => a + l.row.cap, 0),   // real market cap, whatever the sizing mode
        value: leaves.reduce((a, l) => a + l.value, 0),
        children: leaves.map((l) => ({ ...l, itemStyle: { color: perfColor(l.row.returns[period], period, c) } })),
      }))
      .sort((a, b) => b.value - a.value);

    return {
      animation: false,
      tooltip: {
        ...tooltipStyle(c), confine: true,
        formatter: (p: unknown) => {
          const d = (p as { data: Partial<Leaf> & { name: string; value: number; cap?: number; children?: unknown[] } }).data;
          if (!d.row) {
            const n = d.children?.length ?? 0;
            return `<b>${esc(d.name)}</b><br/>${n} companies${d.cap != null ? ` · ${fmtCap(d.cap)}` : ""}`;
          }
          const r = d.row;
          const cells = TOOLTIP_PERIODS.map((k) => `${k} <b>${signed(r.returns[k], 1)}</b>`).join(" &nbsp; ");
          return `<b>${esc(r.name)}</b> <span style="opacity:.7">${esc(r.t)}</span><br/>`
            + `${esc(r.sector)} · ${fmtCap(r.cap)} · $${r.price.toLocaleString("en-US")}<br/>${cells}<br/>`
            + `<span style="opacity:.7">price return · as of ${esc(data.asof)} · ${coarse() ? "tap again" : "click"} for details</span>`;
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
            const w = Math.sqrt((weight(d.row) / total) * area * 0.55);   // approx. side of this (near-square) rectangle, px
            const pct = signed(d.row.returns[period], 1);
            const need = Math.max(d.row.t.length, pct.length) * CHAR_PX + PAD_PX;
            if (w >= need && w >= 30) return `${d.row.t}\n${pct}`;
            return w >= d.row.t.length * CHAR_PX + PAD_PX ? d.row.t : "";
          },
        },
        upperLabel: {
          show: true, height: 16, color: c.ink, fontSize: 10, fontWeight: 600, padding: [0, 0, 0, 3],
          formatter: "{b}", overflow: "truncate", ellipsis: "…",
        },
        levels: [   // [0] is ECharts' invisible root, [1] the sectors, [2] the companies
          { itemStyle: { borderWidth: 0, gapWidth: 0 }, upperLabel: { show: false } },
          { itemStyle: { color: c.surface2, borderColor: c.surface2, borderWidth: 0, gapWidth: 3 } },
          { itemStyle: { borderWidth: 0, gapWidth: 1 }, upperLabel: { show: false } },
        ],
        emphasis: { disabled: false, itemStyle: { borderColor: c.ink, borderWidth: 1 } },
        data: tree,
      }],
    } as EChartsOption;
  }, [data, period, area, total, weight, size]);

  // Mouse: a click opens the detail card. Touch: the first tap must show the tooltip (the only way to read
  // the unlabelled cells), so only a second tap on the same company opens the card.
  const lastTap = useRef<string | null>(null);
  const onClick = useCallback((d: unknown) => {
    const t = (d as { t?: string } | undefined)?.t;
    if (!t) return;
    if (coarse() && lastTap.current !== t) { lastTap.current = t; return; }
    lastTap.current = null;
    onPick(t);
  }, [onPick]);

  return (
    <div ref={box} className="relative flex-1 min-h-112 md:min-h-80 w-full">
      <LazyEChart build={build} onClick={onClick} className="absolute inset-0"
        ariaLabel={`S&P 500 heat map: ${data.rows.length} companies sized by ${SIZE_NAME[size]}, coloured by ${period} price return. A data table follows.`} />
    </div>
  );
}
