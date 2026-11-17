import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { tooltipStyle, type ChartColors, type EChartsOption } from "../components/chartTheme";
import { LazyEChart } from "../components/LazyEChart";
import { TickerModal } from "../components/TickerModal";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { levelBg, levelColor, perfLevel, perfScale, signed } from "../lib/format";
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
  const opts: [HeatSize, string][] = [["cap", "Mkt cap"], ["sqrt", "Balanced"], ["equal", "Equal wt"]];
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

/** Colour key: seven discrete levels, each step a third of the period's saturation point. */
function Legend({ period }: { period: Period }) {
  const step = perfScale(period) / 3;
  const fmt = (n: number) => signed(n * step, step < 1 ? 1 : 0, "%");
  return (
    <span className="inline-flex items-center gap-1" aria-hidden="true">
      <span>Loss</span>
      {[-3, -2, -1, 0, 1, 2, 3].map((l) => (
        <span key={l} className="num inline-block min-w-9 px-1 text-center rounded-sm text-[10px]"
          style={{ background: levelBg(l), color: "var(--ink)" }}>{l === 0 ? "0" : fmt(l)}</span>
      ))}
      <span>Gain · {period}</span>
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

/**
 * Label sizing: every tile gets the largest ticker (+ signed %) that fits its estimated side, from huge
 * on AAPL down to 5px on the smallest tiles. ECharts rich-text styles are static, so we pre-declare one
 * ticker style and one percent style per font-size tier and pick the tier per tile.
 */
const TIERS = [60, 44, 32, 24, 18, 14, 12, 10, 9, 8, 7, 6, 5];
const pctTier = (t: number) => Math.max(5, Math.round(t * 0.55));
const GLYPH_CAPS = 0.82;   // bold capitals (W, M, O...) are wide: width as a fraction of font size
const GLYPH_NUM = 0.64;    // digits, signs and the % sign

/** The label that fits a `w` x `h` px tile: ticker + signed % if both fit, else the ticker alone, else nothing. */
function labelFor(ticker: string, pct: string, w: number, h: number): string {
  for (const t of TIERS) {   // largest first: prefer ticker + percent on two lines
    const p = pctTier(t);
    const need = Math.max(ticker.length * t * GLYPH_CAPS, pct.length * p * GLYPH_NUM) + 6;
    if (need <= w && t * 1.15 + p * 1.2 + 3 <= h) return `{t${t}|${ticker}}
{p${t}|${pct}}`;
  }
  for (const t of TIERS) if (ticker.length * t * GLYPH_CAPS + 6 <= w && t * 1.2 + 3 <= h) return `{t${t}|${ticker}}`;
  return "";
}

/** Real tile sizes (px) from the rendered treemap, keyed by ticker: width, height. */
type Rects = Record<string, [number, number]>;
function readRects(chart: unknown, rows: SP500Row[]): Rects {
  const out: Rects = {};
  // ECharts exposes each node's final layout through the series data; there is no typed API for treemaps.
  type Layout = { width?: number; height?: number } | undefined;
  type SeriesData = { indexOfName: (n: string) => number; getItemLayout: (i: number) => Layout };
  const model = (chart as { getModel?: () => { getSeriesByIndex?: (i: number) => { getData: () => SeriesData } | undefined } | undefined })
    .getModel?.();
  const data = model?.getSeriesByIndex?.(0)?.getData();
  if (!data) return out;   // chart disposed or not laid out yet
  for (const r of rows) {
    const l = data.getItemLayout(data.indexOfName(r.t));
    if (l?.width != null && l.height != null) out[r.t] = [Math.round(l.width), Math.round(l.height)];
  }
  return out;
}

const RICH = Object.fromEntries(TIERS.flatMap((t) => [
  [`t${t}`, { fontSize: t, fontWeight: 700, lineHeight: Math.round(t * 1.15), align: "center" }],
  [`p${t}`, { fontSize: pctTier(t), fontWeight: 500, lineHeight: Math.round(pctTier(t) * 1.2), align: "center" }],
]));

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
  const [rects, setRects] = useState<Rects>({});
  const sig = useRef("");
  const onRendered = useCallback((chart: unknown) => {
    const next = readRects(chart, data.rows);
    const s = Object.values(next).map((v) => v.join("x")).join(",");
    if (s !== sig.current) { sig.current = s; setRects(next); }   // labels depend on tile sizes: re-render once, then settle
  }, [data]);
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
        children: leaves.map((l) => ({ ...l, itemStyle: { color: levelColor(perfLevel(l.row.returns[period], period), c) } })),
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
          show: true, color: c.ink, overflow: "none", rich: RICH,
          formatter: (p: unknown) => {
            const d = (p as { data: Partial<Leaf> }).data;
            if (!d.row) return "";
            const r = rects[d.row.t];
            const side = Math.sqrt((weight(d.row) / total) * area) * 0.9;   // first paint only: assume a square tile
            return labelFor(d.row.t, signed(d.row.returns[period], 1), r ? r[0] : side, r ? r[1] : side);
          },
        },
        upperLabel: {
          show: true, height: 15, color: c.ink2, fontSize: 9, fontWeight: 700, padding: [0, 0, 0, 3],
          formatter: (p: unknown) => String((p as { name: string }).name).toUpperCase(), overflow: "truncate", ellipsis: "…",
        },
        levels: [   // [0] is ECharts' invisible root, [1] the sectors, [2] the companies
          { itemStyle: { borderWidth: 0, gapWidth: 0 }, upperLabel: { show: false } },
          { itemStyle: { color: c.surface, borderColor: c.surface, borderWidth: 0, gapWidth: 3 } },
          { itemStyle: { borderColor: c.surface, borderWidth: 0, gapWidth: 1 }, upperLabel: { show: false } },
        ],
        emphasis: { disabled: false, itemStyle: { borderColor: c.ink, borderWidth: 1 } },
        data: tree,
      }],
    } as EChartsOption;
  }, [data, period, area, total, weight, size, rects]);

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
      <LazyEChart build={build} onClick={onClick} onRendered={onRendered} className="absolute inset-0"
        ariaLabel={`S&P 500 heat map: ${data.rows.length} companies sized by ${SIZE_NAME[size]}, coloured by ${period} price return. A data table follows.`} />
    </div>
  );
}
