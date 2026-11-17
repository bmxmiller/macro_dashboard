import { useMemo } from "react";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { fmtDate, safeUrl, signed } from "../lib/format";
import { useStale } from "../lib/stale";
import type { Earnings, EarningsItem } from "../types";

type Timing = NonNullable<EarningsItem["time"]>;
const TIMING: Record<Timing, string> = {
  BMO: "Before market open",
  AMC: "After market close",
  DMH: "During market hours",
};

/**
 * Implied YoY EPS growth from the consensus estimate vs the same quarter last year.
 * "n/m" (not meaningful) when the base is ≤ 0 or tiny (|prior| < $0.05) or the sign
 * flips; display is capped at ±999%.
 */
function yoyGrowth(e: EarningsItem): { value: number | null; text: string } {
  const est = e.eps_estimate, prior = e.eps_prior_year;
  if (est == null || prior == null) return { value: null, text: "–" };
  if (prior <= 0 || Math.abs(prior) < 0.05 || est < 0) return { value: null, text: "n/m" };
  const g = ((est - prior) / prior) * 100;
  const capped = Math.max(-999, Math.min(999, g));
  return { value: g, text: `${Math.abs(g) > 999 ? (g > 0 ? ">" : "<") : ""}${signed(capped, 0, "%")}` };
}

/** Viewer's local date as YYYY-MM-DD. */
const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
};

const eps = (v: number | null) => (v == null ? "–" : `${v < 0 ? "−" : ""}$${Math.abs(v).toFixed(2)}`);

/** Upcoming earnings for the largest S&P 500 companies, grouped by date. */
export function EarningsCalendar() {
  const { data, error } = useData<Earnings>("earnings");
  const stale = useStale("earnings");

  const byDate = useMemo(() => {
    const m = new Map<string, EarningsItem[]>();
    const today = todayIso(); // stale JSON must never show past reports as upcoming
    const upcoming = (data?.items ?? []).filter((e) => e.date >= today);
    for (const e of upcoming.sort((a, b) => a.date.localeCompare(b.date))) {
      m.set(e.date, [...(m.get(e.date) ?? []), e]);
    }
    return [...m.entries()];
  }, [data]);

  return (
    <Panel id="earnings_calendar" title="Earnings Calendar"
      subtitle={data ? `Next ${data.window_days} days · top ${data.universe_size} S&P 500` : undefined}
      about={data?.about} sourceUrl="https://finance.yahoo.com/calendar/earnings" stale={stale} updatedSection="earnings"
      aboutExtra={data && data.failed.length > 0 && (
        <p className="m-0 text-[11px]" style={{ color: "var(--muted)" }}>
          No calendar data on the last update for: {data.failed.join(", ")}.
        </p>
      )}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && byDate.length === 0 && (
        <PanelMessage>No reports from the {data.universe_size} tracked companies in the next {data.window_days} days.</PanelMessage>
      )}
      {byDate.length > 0 && (
        <table className="w-full border-collapse">
          <thead>
            <tr className="text-[9.5px] font-semibold uppercase tracking-wide whitespace-nowrap" style={{ color: "var(--muted)" }}>
              <th scope="col" className="text-left font-semibold pl-3 pt-2 pb-1">Company</th>
              <th scope="col" className="text-right font-semibold px-1 pt-2 pb-1" title="Consensus EPS estimate">Est. EPS</th>
              <th scope="col" className="text-right font-semibold px-1 pt-2 pb-1" title="Reported EPS for the same quarter a year earlier">Yr ago</th>
              <th scope="col" className="text-right font-semibold pr-3 pl-1 pt-2 pb-1" title="Implied year-on-year EPS growth">YoY</th>
            </tr>
          </thead>
          {byDate.map(([date, items]) => (
            <tbody key={date}>
              <tr>
                <th scope="colgroup" colSpan={4} className="group-label text-left px-3 pt-2 pb-1">
                  {fmtDate(date, { weekday: "short", month: "short", day: "numeric" })}
                </th>
              </tr>
              {items.map((e) => <EarningsRow key={e.ticker} item={e} />)}
            </tbody>
          ))}
        </table>
      )}
    </Panel>
  );
}

function EarningsRow({ item: e }: { item: EarningsItem }) {
  const g = yoyGrowth(e);
  const gColour = g.value == null ? "var(--muted)" : g.value >= 0 ? "var(--pos-ink)" : "var(--neg-ink)";
  const href = safeUrl(e.source_url);
  return (
    <tr className="border-t" style={{ borderColor: "var(--border)" }}>
      <td className="pl-3 pr-1 py-[5px] max-w-0 w-full">
        <div className="flex items-center gap-1.5 min-w-0">
          {href
            ? <a href={href} target="_blank" rel="noopener noreferrer" className="mono font-bold hover:underline"
                style={{ color: "var(--ink)" }} aria-label={`${e.ticker} (${e.name}) on Yahoo Finance`}>{e.ticker}</a>
            : <span className="mono font-bold" style={{ color: "var(--ink)" }}>{e.ticker}</span>}
          <span className="truncate" style={{ color: "var(--ink-2)" }}>{e.name}</span>
          {e.time && <TimingBadge time={e.time} />}
        </div>
      </td>
      <td className="px-1 text-right num font-semibold whitespace-nowrap" style={{ color: "var(--ink)" }}>{eps(e.eps_estimate)}</td>
      <td className="px-1 text-right num whitespace-nowrap" style={{ color: "var(--muted)" }}
        title={e.prior_year_date ? `Reported ${e.prior_year_date}` : undefined}>{eps(e.eps_prior_year)}</td>
      <td className="pr-3 pl-1 text-right num font-bold whitespace-nowrap" style={{ color: gColour }}
        title={g.text === "n/m" ? "Not meaningful: prior-year EPS is negative, near zero, or the sign changes" : undefined}>
        {g.text}
      </td>
    </tr>
  );
}

function TimingBadge({ time }: { time: Timing }) {
  return (
    <span title={TIMING[time]}
      className="shrink-0 ml-auto text-[8.5px] font-extrabold px-1 rounded-sm border"
      style={{ color: "var(--ink-2)", borderColor: "var(--border)", background: "var(--surface-2)" }}>
      <span aria-hidden>{time}</span><span className="sr-only">{TIMING[time]}</span>
    </span>
  );
}
