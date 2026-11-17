import { Panel, PanelMessage } from "../components/Panel";
import { Sparkline } from "../components/Sparkline";
import { useData } from "../lib/data";
import { fmtPrice, fmtReturn, perfBg } from "../lib/format";
import { useStale } from "../lib/stale";
import type { MarketRow, Markets } from "../types";

/** Strip of compact tiles: price, 1D change and a sparkline for headline markets. */
export function IndexSnapshot() {
  const { data, error } = useData<Markets>("markets");
  const stale = useStale("markets");
  const panel = data?.panels.index_snapshot;
  const rows = panel?.groups.flatMap((g) => g.rows) ?? [];

  return (
    <Panel id="index_snapshot" title={panel?.title ?? "Index Snapshot"} subtitle="Last close · 1D change"
      about={panel?.about} stale={stale} updatedSection="markets">
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {rows.length > 0 && (
        <ul className="grid gap-1.5 p-2 m-0 list-none"
          style={{ gridTemplateColumns: "repeat(auto-fill, minmax(150px, 1fr))" }}>
          {rows.map((r) => <Tile key={r.ticker} row={r} />)}
        </ul>
      )}
    </Panel>
  );
}

function Tile({ row: r }: { row: MarketRow }) {
  const d1 = r.returns["1D"];
  const unitSuffix = r.units === "%" ? "%" : "";
  const unitTag = r.units && r.units !== "%" ? r.units : null;
  return (
    <li>
      <a href={r.source_url} target="_blank" rel="noopener noreferrer"
        aria-label={`${r.name}: ${fmtPrice(r.price)}${unitSuffix}, ${fmtReturn(d1, r.mode)} today`}
        className="block rounded px-2 py-1.5 border hover:brightness-110"
        style={{ background: perfBg(d1, "1D", r.mode), borderColor: "var(--border)", color: "var(--ink)" }}>
        <div className="flex items-baseline gap-1.5 min-w-0">
          <span className="font-semibold truncate">{r.name}</span>
          {r.tag && <span className="text-[9px] font-medium uppercase shrink-0" style={{ color: "var(--ink-2)" }}>{r.tag}</span>}
        </div>
        <div className="flex items-end justify-between gap-1 mt-0.5">
          <div className="min-w-0">
            <div className="num text-[14px] font-bold leading-tight">
              {fmtPrice(r.price)}{unitSuffix}
              {unitTag && <span className="text-[9px] font-medium ml-1" style={{ color: "var(--ink-2)" }}>{unitTag}</span>}
            </div>
            <div className="num text-[11px] font-bold">{fmtReturn(d1, r.mode)}</div>
          </div>
          <Sparkline data={r.spark} width={60} height={24} />
        </div>
      </a>
    </li>
  );
}
