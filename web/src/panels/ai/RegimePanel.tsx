import { Panel } from "../../components/Panel";
import { signed } from "../../lib/format";
import type { About, GrowthInflation, Quadrant, RegimeSignal } from "../../types";
import { AiBadge, Disclaimer, InsightsState, SectionLabel, useInsights } from "./shared";

const FALLBACK_ABOUT: About = {
  what: "Rule-based macro regime lenses computed by code: Growth × Inflation, Growth × Policy and Credit × Duration.",
  why: "Asset classes have historically behaved differently depending on the growth/inflation mix, policy stance and credit leadership.",
  how_to_read: "Scores run from −1 to +1; above 0 means rising. The AI text explains the result but never sets it. Not investment advice.",
};

/** Grid layout: x = growth (left down, right up), y = inflation (top up, bottom down). */
const CELLS: { q: Quadrant; growth: "up" | "down"; infl: "up" | "down" }[] = [
  { q: "Stagflation", growth: "down", infl: "up" },
  { q: "Reflation", growth: "up", infl: "up" },
  { q: "Deflationary slowdown", growth: "down", infl: "down" },
  { q: "Goldilocks", growth: "up", infl: "down" },
];

const clamp = (v: number) => Math.max(-1, Math.min(1, v));
const arrow = (d: "up" | "down" | null) => (d === "up" ? "↑" : d === "down" ? "↓" : "–");

function QuadrantGrid({ gi }: { gi: GrowthInflation }) {
  const g = gi.growth.score, i = gi.inflation.score;
  const hasPoint = g != null && i != null;
  return (
    <div className="px-3 pt-1">
      <div className="flex gap-1.5">
        <div className="flex items-center text-[9.5px] font-bold uppercase tracking-wide [writing-mode:vertical-rl] rotate-180"
          style={{ color: "var(--muted)" }}>Inflation ↑</div>
        <div className="relative flex-1 grid grid-cols-2 grid-rows-2 gap-px rounded-sm overflow-hidden aspect-[2/1] min-h-[120px]"
          style={{ background: "var(--border)" }} role="img"
          aria-label={`Growth × Inflation grid. Current quadrant: ${gi.quadrant ?? "unknown"}. Growth score ${g ?? "n/a"}, inflation score ${i ?? "n/a"}.`}>
          {CELLS.map((c) => {
            const active = c.q === gi.quadrant;
            return (
              <div key={c.q} className="flex flex-col items-center justify-center text-center p-1"
                style={{
                  background: active ? "color-mix(in oklab, var(--accent) 28%, var(--surface))" : "var(--surface-2)",
                  outline: active ? "2px solid var(--accent)" : undefined, outlineOffset: -2,
                }}>
                <span className={`text-[11px] leading-tight ${active ? "font-extrabold" : "font-semibold"}`}
                  style={{ color: active ? "var(--ink)" : "var(--muted)" }}>{c.q}</span>
                <span className="text-[9px]" style={{ color: "var(--muted)" }}>
                  growth {arrow(c.growth)} · inflation {arrow(c.infl)}
                </span>
                {active && <span className="mt-0.5 text-[9px] font-bold uppercase tracking-wide" style={{ color: "var(--ink)" }}>● Current</span>}
              </div>
            );
          })}
          {hasPoint && (
            <span aria-hidden className="absolute w-3 h-3 rounded-full border-2 -translate-x-1/2 -translate-y-1/2"
              style={{
                left: `${((clamp(g) + 1) / 2) * 100}%`, top: `${((1 - clamp(i)) / 2) * 100}%`,
                background: "var(--ink)", borderColor: "var(--surface)",
              }} />
          )}
        </div>
      </div>
      <div className="text-right text-[9.5px] font-bold uppercase tracking-wide pt-0.5" style={{ color: "var(--muted)" }}>Growth →</div>
      {gi.borderline && (
        <div className="text-[10.5px]" style={{ color: "var(--ink-2)" }}>Borderline: a score is within ±0.1 of zero, so the quadrant could flip on small data changes.</div>
      )}
    </div>
  );
}

function SignalRows({ name, s }: { name: string; s: RegimeSignal }) {
  return (
    <div className="px-3 py-1">
      <div className="flex items-baseline justify-between text-[11.5px] font-bold" style={{ color: "var(--ink)" }}>
        <span>{name} {arrow(s.direction)}</span>
        <span className="num">score {signed(s.score, 2, "")}</span>
      </div>
      {s.components.map((c) => (
        <div key={c.id} className="flex items-baseline justify-between gap-2 text-[10.5px]" style={{ color: "var(--ink-2)" }}>
          <span className="truncate" title={c.label}>{c.label}</span>
          <span className="num whitespace-nowrap">
            {signed(c.value, c.units === "%" ? 1 : 2, c.units === "%" ? "%" : "pp")}
            <span style={{ color: "var(--muted)" }}> → {signed(c.score, 2, "")}</span>
          </span>
        </div>
      ))}
      {s.components.length === 0 && <div className="text-[10.5px]" style={{ color: "var(--muted)" }}>Insufficient data</div>}
    </div>
  );
}

function LensRow({ title, label, detail }: { title: string; label: string | null; detail: string }) {
  return (
    <div className="px-3 py-1.5 border-t" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>{title}</span>
        <span className="text-[12px] font-bold text-right" style={{ color: "var(--ink)" }}>{label ?? "Insufficient data"}</span>
      </div>
      {detail && <div className="num text-[10.5px] text-right" style={{ color: "var(--ink-2)" }}>{detail}</div>}
    </div>
  );
}

/** Rule-based macro regime (code) + AI explainer (text). */
export function RegimePanel() {
  const { data, error, stale, note } = useInsights();
  const r = data?.regime;
  const gp = r?.growth_policy;
  const cd = r?.credit_duration;

  return (
    <Panel id="macro_regime" title="Macro Regime" subtitle="Rule-based lenses · AI explainer"
      about={data?.about.regime ?? FALLBACK_ABOUT} stale={stale}>
      <InsightsState data={data} error={error} />
      {data && r && gp && cd && (
        <>
          <AiBadge data={data} note={note} />
          <SectionLabel>Growth × Inflation{r.growth_inflation.quadrant ? ` · ${r.growth_inflation.quadrant}` : ""}</SectionLabel>
          <QuadrantGrid gi={r.growth_inflation} />
          <SignalRows name="Growth" s={r.growth_inflation.growth} />
          <SignalRows name="Inflation" s={r.growth_inflation.inflation} />

          <div className="mt-1.5">
            <LensRow title="Growth × Policy" label={gp.label}
              detail={gp.real_rate != null
                ? `Real rate ${signed(gp.real_rate, 2, "%")} = Fed funds ${gp.fed_funds?.toFixed(2)}% − core PCE ${gp.core_pce?.toFixed(1)}% · neutral ${gp.neutral_band[0]}–${gp.neutral_band[1]}%`
                : ""} />
            <LensRow title={`Credit × Duration · ${cd.period}`} label={cd.label}
              detail={cd.pairs.map((p) => `${p.long} ${signed(p.long_ret)} vs ${p.short} ${signed(p.short_ret)} = ${signed(p.spread, 1, "pp")}`).join(" · ")} />
          </div>

          <SectionLabel>Why (AI explainer)</SectionLabel>
          <p className="m-0 px-3 text-[12px] leading-snug" style={{ color: "var(--ink-2)" }}>{r.explainer.rationale}</p>
          <SectionLabel>Historical tendencies</SectionLabel>
          <ul className="m-0 pl-7 pr-3 space-y-0.5 text-[11.5px] leading-snug" style={{ color: "var(--ink-2)" }}>
            {r.explainer.asset_tendencies.map((t, k) => <li key={k}>{t}</li>)}
          </ul>
          <SectionLabel>Caveats</SectionLabel>
          <ul className="m-0 pl-7 pr-3 pb-2 space-y-0.5 text-[11.5px] leading-snug" style={{ color: "var(--ink-2)" }}>
            {r.explainer.caveats.map((t, k) => <li key={k}>{t}</li>)}
          </ul>
          <Disclaimer text={data.disclaimer} />
        </>
      )}
    </Panel>
  );
}
