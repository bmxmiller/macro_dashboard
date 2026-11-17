import { useCallback, useState, type MouseEvent } from "react";
import { fmtValue, signed } from "../lib/format";
import type { Metric } from "../types";
import { AboutButton } from "./AboutCard";
import { HistoryModal } from "./HistoryModal";
import { changeSuffix, MetricStats } from "./MetricStats";
import { Sparkline } from "./Sparkline";
import { metricView, ViewToggle } from "./ViewToggle";

/** Stable empty default: a new [] each render would rebuild the chart option and reset zoom. */
const EMPTY: [string, string][] = [];

/**
 * Grouped list of macro metrics (latest print vs previous). Each row has a
 * good/bad arrow, an ⓘ About card with 10y stats, and opens its history chart.
 * Shared by the US Economic Indicators and UK Macro panels.
 */
export function MetricList({ groups, metrics, recessions = EMPTY }: {
  groups: { id: string; label: string }[];
  metrics: Metric[];
  recessions?: [string, string][];
}) {
  const [open, setOpen] = useState<Metric | null>(null);
  const [alt, setAlt] = useState<Record<string, boolean>>({});  // metric id -> showing the alternative view
  const close = useCallback(() => setOpen(null), []);
  const setView = (id: string, v: boolean) => setAlt((a) => ({ ...a, [id]: v }));

  return (
    <>
      {groups.map((g) => {
        const ms = metrics.filter((m) => m.group === g.id);
        if (!ms.length) return null;
        return (
          <div key={g.id}>
            <div className="group-label px-3 pt-2.5 pb-1 sticky top-0 z-[1]" style={{ background: "var(--surface)" }}>
              {g.label}
            </div>
            {ms.map((m) => (
              <MetricRow key={m.id} metric={m} useAlt={!!alt[m.id]} onView={(v) => setView(m.id, v)}
                onOpen={() => setOpen(m)} />
            ))}
          </div>
        );
      })}
      {open && (
        <HistoryModal metric={metricView(open, !!alt[open.id])} recessions={recessions} onClose={close}
          viewToggle={<ViewToggle metric={open} useAlt={!!alt[open.id]} onChange={(v) => setView(open.id, v)} />} />
      )}
    </>
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

function MetricRow({ metric: base, useAlt, onView, onOpen }: {
  metric: Metric; useAlt: boolean; onView: (alt: boolean) => void; onOpen: () => void;
}) {
  const m = metricView(base, useAlt);
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
      <div className="hidden sm:flex flex-col items-end gap-0.5 shrink-0">
        <ViewToggle metric={base} useAlt={useAlt} onChange={onView} />
        <span title="Last 24 observations" aria-hidden><Sparkline data={m.history.slice(-24).map((h) => h[1])} width={56} height={18} neutral /></span>
      </div>
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
