import { useCallback, useState, type MouseEvent } from "react";
import { AboutButton } from "../components/AboutCard";
import { HistoryModal } from "../components/HistoryModal";
import { changeSuffix, MetricStats } from "../components/MetricStats";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { fmtValue, signed } from "../lib/format";
import { useStale } from "../lib/stale";
import type { About, Economy, Metric } from "../types";

const ABOUT: About = {
  what: "Headline US macro data across inflation, the labour market, activity, the consumer, policy and credit, pulled from FRED and the original statistical agencies.",
  why: "These releases drive Fed expectations, bond yields and the earnings outlook. Seeing them side by side shows whether the economy is heating up or cooling down.",
  how_to_read: "The arrow compares the latest print with the previous one. Green means the move is benign for the economy and red means it is not (grey: no clear good direction). It is not an investment signal. Click a row for its full history with recessions shaded, or ⓘ for what the metric means.",
};

/** Grouped list of macro metrics; each row opens its history chart. */
export function EconomicIndicators() {
  const { data, error } = useData<Economy>("economy");
  const stale = useStale("economy");
  const [open, setOpen] = useState<Metric | null>(null);
  const close = useCallback(() => setOpen(null), []);

  return (
    <Panel id="economic_indicators" title="Economic Indicators" subtitle="Latest print vs. previous"
      about={ABOUT} sourceUrl="https://fred.stlouisfed.org/" stale={stale}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data?.groups.map((g) => {
        const ms = data.metrics.filter((m) => m.group === g.id);
        if (!ms.length) return null;
        return (
          <div key={g.id}>
            <div className="group-label px-3 pt-2.5 pb-1 sticky top-0 z-[1]" style={{ background: "var(--surface)" }}>
              {g.label}
            </div>
            {ms.map((m) => <MetricRow key={m.id} metric={m} onOpen={() => setOpen(m)} />)}
          </div>
        );
      })}
      {open && data && <HistoryModal metric={open} recessions={data.recessions} onClose={close} />}
    </Panel>
  );
}

/** Latest minus previous, rounded to display precision (so "−0.0" never appears). */
function roundedChange(m: Metric): number | null {
  if (m.value == null || m.prev == null) return null;
  const f = 10 ** m.decimals;
  return Math.round((m.value - m.prev) * f) / f || 0;
}

function trend(change: number | null, good: Metric["good"]): { arrow: string; colour: string; word: string } {
  if (!change) return { arrow: "▬", colour: "var(--muted)", word: "unchanged" };
  const up = change > 0;
  const word = up ? "up" : "down";
  if (good === "neutral") return { arrow: up ? "▲" : "▼", colour: "var(--muted)", word };
  const isGood = (good === "up") === up;
  return { arrow: up ? "▲" : "▼", colour: isGood ? "var(--pos-ink)" : "var(--neg-ink)", word: `${word}, ${isGood ? "favourable" : "unfavourable"}` };
}

function MetricRow({ metric: m, onOpen }: { metric: Metric; onOpen: () => void }) {
  const change = roundedChange(m);
  const t = trend(change, m.good);
  // Clicks inside the portalled About popover bubble through React; ignore those.
  const onClick = (e: MouseEvent<HTMLDivElement>) => {
    if (e.currentTarget.contains(e.target as Node)) onOpen();
  };
  return (
    <div onClick={onClick} className="group flex items-center gap-2 pl-3 pr-1.5 py-1.5 border-t cursor-pointer hover:bg-[var(--surface-2)]"
      style={{ borderColor: "var(--border)" }}>
      <button type="button" className="min-w-0 flex-1 text-left" aria-label={`${m.name}: show history`}>
        <div className="text-[10px] font-semibold uppercase tracking-wide truncate" style={{ color: "var(--ink-2)" }}>
          {m.name} <span style={{ color: "var(--muted)" }}>({m.period_label ?? "–"})</span>
        </div>
        <div className="num text-[17px] font-bold leading-tight" style={{ color: "var(--ink)" }}>
          {fmtValue(m.value, m.decimals, m.units)}
        </div>
      </button>
      <div className="text-right shrink-0 num">
        <div className="text-[11px] font-bold" style={{ color: t.colour }}>
          <span aria-label={t.word} title={t.word}>{t.arrow}</span>{" "}
          {signed(change, m.decimals, changeSuffix(m.units))}
        </div>
        <div className="text-[10px]" style={{ color: "var(--muted)" }}>prev {fmtValue(m.prev, m.decimals, m.units)}</div>
      </div>
      <AboutButton title={m.name} about={m.about} sourceUrl={m.source_url} extra={<MetricStats metric={m} />} />
    </div>
  );
}
