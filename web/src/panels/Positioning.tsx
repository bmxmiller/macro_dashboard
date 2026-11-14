import { useMemo } from "react";
import { AboutButton } from "../components/AboutCard";
import { ExternalIcon } from "../components/Icons";
import { Panel, PanelMessage } from "../components/Panel";
import { Sparkline } from "../components/Sparkline";
import { useData } from "../lib/data";
import { fmtDate, ordinal, signed, signedCompact } from "../lib/format";
import { useStale } from "../lib/stale";
import type { CotMarket, Positioning as PositioningData } from "../types";

/** CFTC Commitments of Traders: speculative net positioning per futures market. */
export function Positioning() {
  const { data, error } = useData<PositioningData>("positioning");
  const stale = useStale("positioning");
  const asof = data?.report_date ? ` · as of ${fmtDate(data.report_date, { month: "short", day: "numeric", year: "numeric" })}` : "";

  return (
    <Panel id="positioning" title="Futures Positioning" subtitle={`CFTC COT · speculators' net${asof}`}
      about={data?.about} sourceUrl={data?.source_url} stale={stale}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && data.markets.length === 0 && <PanelMessage>No positioning data available.</PanelMessage>}
      {data && data.markets.length > 0 && (
        <>
          <div className="flex justify-between px-3 pt-2 pb-1 text-[9.5px] font-semibold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
            <span>Market · net contracts (w/w)</span><span>3y percentile</span>
          </div>
          <ul className="m-0 p-0 list-none">
            {data.markets.map((m) => <MarketRow key={m.id} market={m} />)}
          </ul>
        </>
      )}
    </Panel>
  );
}

function MarketRow({ market: m }: { market: CotMarket }) {
  const spark = useMemo(() => m.history.map(([, v]) => v), [m.history]);
  const wowColour = m.change_wow ? (m.change_wow > 0 ? "var(--pos-ink)" : "var(--neg-ink)") : "var(--muted)";
  return (
    <li className="pl-3 pr-1.5 py-1.5 border-t" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-baseline gap-1.5">
        <span className="font-semibold truncate" style={{ color: "var(--ink)" }}>{m.name}</span>
        <span className="text-[9px] font-semibold uppercase tracking-wide whitespace-nowrap" style={{ color: "var(--muted)" }}>
          {m.trader_group}
        </span>
        <span className="ml-auto num font-bold whitespace-nowrap" style={{ color: "var(--ink)" }}
          title={`Net ${m.net.toLocaleString("en-US")} contracts`}>
          {signedCompact(m.net)}
        </span>
        <span className="num text-[10px] font-semibold whitespace-nowrap" style={{ color: wowColour }}
          title="Change in net contracts versus the previous week">
          ({signedCompact(m.change_wow)} w/w)
        </span>
      </div>
      <div className="flex items-center gap-2 mt-1">
        <PercentileBar value={m.percentile_3y} name={m.name} />
        <span title={`Weekly net position, last ${m.weeks} weeks`}><Sparkline data={spark} width={64} height={18} /></span>
        <AboutButton title={m.name} about={m.about} sourceUrl={m.source_url} extra={<MarketDetails market={m} />} />
      </div>
    </li>
  );
}

/** 0–100 bar with the rank as text; extremes (≤10 / ≥90) are flagged in the label. */
function PercentileBar({ value, name }: { value: number | null; name: string }) {
  const v = value == null ? null : Math.max(0, Math.min(100, value));
  const extreme = v != null && (v <= 10 || v >= 90);
  return (
    <div className="flex-1 flex items-center gap-1.5 min-w-0">
      <div role="meter" aria-valuemin={0} aria-valuemax={100} aria-valuenow={v ?? undefined}
        aria-label={`${name}: 3-year percentile ${v == null ? "not available" : ordinal(v)}`}
        className="relative flex-1 h-2 rounded-sm overflow-hidden" style={{ background: "var(--surface-2)" }}>
        {/* midline marks the 3-year median */}
        <span aria-hidden className="absolute top-0 bottom-0 left-1/2 w-px" style={{ background: "var(--grid)" }} />
        {v != null && (
          <span aria-hidden className="absolute top-0 bottom-0 left-0 rounded-sm"
            style={{ width: `${v}%`, background: extreme ? "var(--accent)" : "color-mix(in oklab, var(--accent) 55%, var(--surface-2))" }} />
        )}
      </div>
      <span className="num text-[10.5px] font-bold w-[34px] text-right" style={{ color: extreme ? "var(--ink)" : "var(--ink-2)" }}>
        {v == null ? "–" : ordinal(v)}
      </span>
    </div>
  );
}

function MarketDetails({ market: m }: { market: CotMarket }) {
  const n = (v: number | null) => (v == null ? "–" : v.toLocaleString("en-US"));
  return (
    <div className="space-y-1.5">
      <div className="group-label">This week ({m.report_date})</div>
      <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-0.5 m-0 num" style={{ color: "var(--ink)" }}>
        <dt style={{ color: "var(--muted)" }}>{m.trader_group} long / short</dt><dd className="m-0">{n(m.long)} / {n(m.short)}</dd>
        <dt style={{ color: "var(--muted)" }}>Net (% of OI)</dt>
        <dd className="m-0">{signedCompact(m.net)} ({signed(m.net_pct_oi, 1, "%")})</dd>
        <dt style={{ color: "var(--muted)" }}>3y range</dt><dd className="m-0">{signedCompact(m.min_3y)} to {signedCompact(m.max_3y)}</dd>
        <dt style={{ color: "var(--muted)" }}>3y percentile</dt><dd className="m-0">{m.percentile_3y == null ? "–" : ordinal(m.percentile_3y)}</dd>
        <dt style={{ color: "var(--muted)" }}>COT index (3y)</dt><dd className="m-0">{m.cot_index_3y == null ? "–" : m.cot_index_3y.toFixed(0)}</dd>
      </dl>
      <p className="m-0 text-[10.5px]" style={{ color: "var(--muted)" }}>
        Percentile: share of the last 3 years' weekly readings at or below this week's net. COT index: position
        within the 3-year min–max range (0 = min, 100 = max), so one extreme week stretches the scale.
      </p>
      <div className="text-[10.5px]" style={{ color: "var(--muted)" }}>{m.report_name} · {m.exchange_name ?? m.contract_code}</div>
      <a href={m.data_url} target="_blank" rel="noopener noreferrer"
        className="inline-flex items-center gap-1 font-medium hover:underline" style={{ color: "var(--accent)" }}>
        Data on CFTC Public Reporting <ExternalIcon />
      </a>
    </div>
  );
}
