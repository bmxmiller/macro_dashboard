import { Panel } from "../../components/Panel";
import { useData } from "../../lib/data";
import { signed } from "../../lib/format";
import { useStale } from "../../lib/stale";
import type { About, GrowthInflation, Quadrant, Regime, RegimeSignal } from "../../types";
import { AiBadge, DataAsOf, Disclaimer, LoadState, SectionLabel, SourceList, useInsights } from "./shared";

const FALLBACK_ABOUT: About = {
  what: "Rule-based macro regime lenses computed by code: a Growth × Inflation momentum quadrant, Growth × Policy and Credit × Duration.",
  why: "Asset classes have historically behaved differently depending on the growth/inflation mix, policy stance and credit leadership.",
  how_to_read: "Scores run from −1 to +1: accelerating at ≥ +0.1, decelerating at ≤ −0.1, otherwise flat. Quadrants describe the direction of change, not the level. Not investment advice.",
};
const DISCLAIMER = "Generalisations about past regimes, not forecasts. Not investment advice.";
const EXPLAINER_MISSING = "AI explainer not generated yet. Add GEMINI_API_KEY / GROQ_API_KEY.";

/** Grid layout: x = growth (left decelerating, right accelerating), y = inflation (top accelerating). */
const CELLS: { q: Quadrant; growth: "up" | "down"; infl: "up" | "down" }[] = [
  { q: "Stagflation", growth: "down", infl: "up" },
  { q: "Inflationary boom", growth: "up", infl: "up" },
  { q: "Disinflationary slowdown", growth: "down", infl: "down" },
  { q: "Goldilocks", growth: "up", infl: "down" },
];

const clamp = (v: number) => Math.max(-1, Math.min(1, v));
const STATE_ARROW = { accelerating: "↑", decelerating: "↓", flat: "→" } as const;
const stateText = (s: RegimeSignal) => (s.state ? `${STATE_ARROW[s.state]} ${s.state}` : "insufficient data");
const fmtUnits = (v: number | null, units: string) =>
  units === "%" ? signed(v, 1, "%") : units === "pp" ? signed(v, 2, "pp") : signed(v, 2, "");

function Tag({ children }: { children: string }) {
  return (
    <span className="ml-1 text-[9px] font-bold uppercase px-1 rounded-sm align-middle"
      style={{ background: "var(--surface-2)", color: "var(--ink-2)" }}>{children}</span>
  );
}

function QuadrantGrid({ gi }: { gi: GrowthInflation }) {
  const g = gi.growth.score, i = gi.inflation.score;
  const hasPoint = g != null && i != null;
  return (
    <div className="px-3 pt-1">
      <div className="flex gap-1.5">
        <div className="flex h-[150px] items-center justify-between text-[9px] font-bold uppercase tracking-wide [writing-mode:vertical-rl] rotate-180"
          style={{ color: "var(--muted)" }}>
          <span>Decelerating</span><span>Inflation</span><span>Accelerating</span>
        </div>
        <div className="relative flex-1 grid grid-cols-2 grid-rows-2 gap-px rounded-sm overflow-hidden h-[150px]"
          style={{ background: "var(--border)" }} role="img"
          aria-label={`Growth × Inflation grid. Current: ${gi.label ?? "unknown"}. Growth score ${g ?? "n/a"}, inflation score ${i ?? "n/a"}.`}>
          {CELLS.map((c) => {
            const active = c.q === gi.quadrant;
            const neighbour = !active && gi.boundary && gi.allowed_quadrants.includes(c.q);
            return (
              <div key={c.q} className="flex flex-col items-center justify-center text-center p-1"
                style={{
                  background: active ? "color-mix(in oklab, var(--accent) 28%, var(--surface))"
                    : neighbour ? "color-mix(in oklab, var(--accent) 12%, var(--surface))" : "var(--surface-2)",
                  outline: active ? "2px solid var(--accent)" : neighbour ? "1px dashed var(--accent)" : undefined,
                  outlineOffset: -2,
                }}>
                <span className={`text-[11px] leading-tight ${active ? "font-extrabold" : "font-semibold"}`}
                  style={{ color: active || neighbour ? "var(--ink)" : "var(--muted)" }}>{c.q}</span>
                <span className="text-[9px]" style={{ color: "var(--muted)" }}>
                  growth {c.growth === "up" ? "↑" : "↓"} · inflation {c.infl === "up" ? "↑" : "↓"}
                </span>
                {active && <span className="mt-0.5 text-[9px] font-bold uppercase tracking-wide" style={{ color: "var(--ink)" }}>● Current</span>}
                {neighbour && <span className="mt-0.5 text-[9px] font-bold uppercase tracking-wide" style={{ color: "var(--ink-2)" }}>Boundary</span>}
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
      <div className="flex justify-between pl-5 pt-0.5 text-[9px] font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>
        <span>← Decelerating</span><span>Growth</span><span>Accelerating →</span>
      </div>
      {gi.level_note && <div className="pt-1 text-[10.5px]" style={{ color: "var(--ink-2)" }}>{gi.level_note}</div>}
    </div>
  );
}

function SignalRows({ name, s }: { name: string; s: RegimeSignal }) {
  return (
    <div className="px-3 py-1">
      <div className="flex items-baseline justify-between text-[11.5px] font-bold" style={{ color: "var(--ink)" }}>
        <span>{name}: {stateText(s)}</span>
        <span className="num">score {signed(s.score, 2, "")}</span>
      </div>
      {s.components.map((c) => (
        <div key={c.id} className="flex items-baseline justify-between gap-2 text-[10.5px]" style={{ color: "var(--ink-2)" }}>
          <span className="truncate" title={`${c.label}${c.asof ? ` (latest ${c.asof})` : ""}`}>{c.label}</span>
          <span className="num whitespace-nowrap">
            {fmtUnits(c.value, c.units)}
            <span style={{ color: "var(--muted)" }}> → {signed(c.score, 2, "")}</span>
          </span>
        </div>
      ))}
    </div>
  );
}

function LensRow({ title, label, borderline, detail }: { title: string; label: string | null; borderline: boolean; detail: string[] }) {
  return (
    <div className="px-3 py-1.5 border-t" style={{ borderColor: "var(--border)" }}>
      <div className="flex items-baseline justify-between gap-2">
        <span className="text-[10px] font-bold uppercase tracking-wide" style={{ color: "var(--muted)" }}>{title}</span>
        <span className="text-[12px] font-bold text-right" style={{ color: "var(--ink)" }}>
          {label ?? "Insufficient data"}{borderline && <Tag>borderline</Tag>}
        </span>
      </div>
      {detail.filter(Boolean).map((d, k) => (
        <div key={k} className="num text-[10.5px] text-right" style={{ color: "var(--ink-2)" }}>{d}</div>
      ))}
    </div>
  );
}

/** Rule-based macro regime (code, regime.json) + optional AI explainer (insights.json). */
export function RegimePanel() {
  const { data: r, error } = useData<Regime>("regime");
  const stale = useStale("regime");
  const ai = useInsights();
  const missing = !r && !!error && error.startsWith("no data yet");
  const gp = r?.growth_policy;
  const cd = r?.credit_duration;
  const ex = ai.data?.regime_explainer;

  return (
    <Panel id="macro_regime" title="Macro Regime" subtitle="Rule-based lenses · AI explainer"
      about={r?.about ?? FALLBACK_ABOUT} sourceUrl={r?.methodology_url}
      aboutExtra={r ? <SourceList sources={r.sources} methodologyUrl={r.methodology_url} /> : undefined} stale={stale}>
      <LoadState ready={!!r} error={missing ? null : error} missing={missing}
        missingMsg="Regime not computed yet: run the pipeline's regime section." />
      {r && gp && cd && (
        <>
          <DataAsOf iso={r.data_asof} />
          <SectionLabel>Growth × Inflation momentum{r.growth_inflation.label ? ` · ${r.growth_inflation.label}` : ""}</SectionLabel>
          <QuadrantGrid gi={r.growth_inflation} />
          <SignalRows name="Growth" s={r.growth_inflation.growth} />
          <SignalRows name="Inflation" s={r.growth_inflation.inflation} />
          {r.stale_inputs.length > 0 && (
            <div className="px-3 text-[10.5px]" style={{ color: "var(--ink-2)" }}>
              Left out (data too old): {r.stale_inputs.join(", ")}
            </div>
          )}

          <div className="mt-1.5">
            <LensRow title="Growth × Policy" label={gp.label} borderline={gp.borderline}
              detail={gp.real_rate_pct != null ? [
                `Real rate ${signed(gp.real_rate_pct, 2, "%")} = Fed funds midpoint ${gp.fed_funds_mid_pct?.toFixed(3)}% − core PCE ${gp.core_pce_pct?.toFixed(2)}%`,
                `Neutral band ${gp.neutral_band_pct[0]}–${gp.neutral_band_pct[1]}%. ${gp.note}`,
              ] : []} />
            <LensRow title={`Credit × Duration · ${cd.period}`} label={cd.label} borderline={cd.borderline}
              detail={[
                cd.pairs.map((p) => `${p.long} ${signed(p.long_ret_pct)} vs ${p.short} ${signed(p.short_ret_pct)} = ${signed(p.spread_pp, 1, "pp")}`).join(" · "),
                cd.hy_oas_3m_chg_bp != null
                  ? `HY spread ${signed(cd.hy_oas_3m_chg_bp, 0, " bp")} over 3M${cd.hy_oas_confirms == null ? "" : cd.hy_oas_confirms ? " (confirms)" : " (does not confirm)"}`
                  : "",
              ]} />
          </div>

          <SectionLabel>Historical tendencies (generalisations, not forecasts)</SectionLabel>
          {r.tendencies.items.length > 0 ? (
            <ul className="m-0 pl-7 pr-3 space-y-0.5 text-[11.5px] leading-snug" style={{ color: "var(--ink-2)" }}>
              {r.tendencies.items.map((t) => <li key={t.id}>{t.text}</li>)}
            </ul>
          ) : <div className="px-3 text-[11px]" style={{ color: "var(--muted)" }}>No quadrant: insufficient data.</div>}
          <div className="px-3 pt-1 text-[10px]" style={{ color: "var(--muted)" }}>Basis: {r.tendencies.basis}</div>
          <Disclaimer text={DISCLAIMER} />

          <div className="border-t" style={{ borderColor: "var(--border)" }}>
            <SectionLabel>Why (AI explainer)</SectionLabel>
            {ai.data && ex ? (
              <>
                <AiBadge data={ai.data} note={ai.note} />
                {ex.regime_generated_at !== r.generated_at && (
                  <div className="px-3 pt-1 text-[10.5px]" style={{ color: "var(--ink-2)" }}>
                    Written for an earlier regime reading{ex.regime_label ? ` (${ex.regime_label})` : ""}.
                  </div>
                )}
                <p className="m-0 px-3 pt-1 text-[12px] leading-snug" style={{ color: "var(--ink-2)" }}>{ex.rationale}</p>
                <SectionLabel>Caveats</SectionLabel>
                <ul className="m-0 pl-7 pr-3 pb-1 space-y-0.5 text-[11.5px] leading-snug" style={{ color: "var(--ink-2)" }}>
                  {ex.caveats.map((t, k) => <li key={k}>{t}</li>)}
                </ul>
                <Disclaimer text={ai.data.disclaimer} />
              </>
            ) : (
              <div className="px-3 pb-2 text-[11px]" style={{ color: "var(--muted)" }}>
                {ai.missing ? EXPLAINER_MISSING : ai.error ? `Could not load the AI explainer: ${ai.error}` : "Loading…"}
              </div>
            )}
          </div>
        </>
      )}
    </Panel>
  );
}
