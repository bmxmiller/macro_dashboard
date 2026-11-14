import { AboutButton } from "../components/AboutCard";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { fmtDate, ordinal, signed } from "../lib/format";
import { useStale } from "../lib/stale";
import type { About, FearGreed, Sentiment as SentimentData, VixTerm } from "../types";

const ABOUT: About = {
  what: "Two gauges of US equity-market mood: CNN's Fear & Greed Index (a 0–100 composite of seven indicators) and the VIX term structure (near-dated vs 3-month implied volatility).",
  why: "Sentiment extremes often mark crowded positioning: extreme fear tends to coincide with forced selling near lows, while extreme greed signals complacency. An inverted VIX curve flags acute near-term stress.",
  how_to_read: "Fear & Greed (on CNN's whole-number bands): 0–24 extreme fear, 25–44 fear, 45–55 neutral, 56–75 greed, 76–100 extreme greed. VIX/VIX3M below 0.95 is the normal upward-sloping curve (contango), 0.95–1.0 is flat and above 1.0 is backwardation. These are contrarian context, not trading signals. Use ⓘ on each block for details.",
};

/** CNN's integer bands: [highest score in band, label, colour] (≤24, 25–44, 45–55, 56–75, ≥76). */
const ZONES: [number, string, string][] = [
  [24, "extreme fear", "var(--neg)"],
  [44, "fear", "color-mix(in oklab, var(--neg) 50%, var(--mid))"],
  [55, "neutral", "var(--grid)"],
  [75, "greed", "color-mix(in oklab, var(--pos) 50%, var(--mid))"],
  [100, "extreme greed", "var(--pos)"],
];

/** Rating for a score, classified on the ROUNDED score as CNN displays it. */
const ratingOf = (v: number) => ZONES.find(([hi]) => Math.round(v) <= hi)?.[1] ?? "extreme greed";

function ratingColour(rating: string | null): string {
  const r = (rating ?? "").toLowerCase();
  if (r.includes("fear")) return "var(--neg-ink)";
  if (r.includes("greed")) return "var(--pos-ink)";
  return "var(--muted)";
}

const cap = (s: string | null | undefined) => (s ? s.charAt(0).toUpperCase() + s.slice(1) : "–");

/** Fear & Greed gauge + components, and the VIX term structure. */
export function Sentiment() {
  const { data, error } = useData<SentimentData>("sentiment");
  const stale = useStale("sentiment");

  return (
    <Panel id="sentiment" title="Market Sentiment" subtitle="CNN Fear & Greed · VIX term structure"
      about={ABOUT} sourceUrl={data?.fear_greed?.source_url ?? "https://www.cnn.com/markets/fear-and-greed"} stale={stale}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && (
        <>
          {data.fear_greed
            ? <FearGreedBlock fg={data.fear_greed} />
            : <PanelMessage>Fear &amp; Greed unavailable{data.fear_greed_error ? `: ${data.fear_greed_error}` : "."}</PanelMessage>}
          {data.vix_term
            ? <VixBlock vt={data.vix_term} />
            : <PanelMessage>VIX term structure unavailable{data.vix_term_error ? `: ${data.vix_term_error}` : "."}</PanelMessage>}
        </>
      )}
    </Panel>
  );
}

function BlockHeader({ label, about, sourceUrl, right }: { label: string; about: About; sourceUrl: string; right?: React.ReactNode }) {
  return (
    <div className="flex items-center gap-1.5 pl-3 pr-1.5 pt-2">
      <span className="group-label">{label}</span>
      <span className="ml-auto text-[10px]" style={{ color: "var(--muted)" }}>{right}</span>
      <AboutButton title={label} about={about} sourceUrl={sourceUrl} />
    </div>
  );
}

function FearGreedBlock({ fg }: { fg: FearGreed }) {
  const prev: [string, number | null][] = [
    ["Prev close", fg.previous_close], ["1 week ago", fg.previous_1_week],
    ["1 month ago", fg.previous_1_month], ["1 year ago", fg.previous_1_year],
  ];
  const asof = fg.asof ? fmtDate(fg.asof.slice(0, 10), { month: "short", day: "numeric" }) : null;
  return (
    <div>
      <BlockHeader label="Fear & Greed Index" about={fg.about} sourceUrl={fg.source_url} right={asof && `as of ${asof}`} />
      <div className="flex items-center gap-2 px-3">
        <Gauge score={fg.score} rating={fg.rating} />
        <dl className="flex-1 grid grid-cols-2 gap-x-2 gap-y-1 m-0">
          {prev.map(([label, v]) => (
            <div key={label}>
              <dt className="text-[9.5px] uppercase tracking-wide" style={{ color: "var(--muted)" }}>{label}</dt>
              <dd className="m-0 num font-bold" style={{ color: "var(--ink)" }}>
                {v == null ? "–" : v.toFixed(0)}{" "}
                {v != null && <span className="text-[9.5px] font-semibold" style={{ color: ratingColour(ratingOf(v)) }}>{cap(ratingOf(v))}</span>}
              </dd>
            </div>
          ))}
        </dl>
      </div>
      <ul className="m-0 mt-1 p-0 list-none" aria-label="Fear & Greed components">
        {fg.components.map((c) => (
          <li key={c.id} className="flex items-center gap-2 px-3 py-[3px] border-t" style={{ borderColor: "var(--border)" }}
            title={c.description ?? undefined}>
            <span className="flex-1 truncate" style={{ color: "var(--ink-2)" }}>{c.name}</span>
            <span className="num font-bold w-[30px] text-right" style={{ color: "var(--ink)" }}>{c.score == null ? "–" : c.score.toFixed(0)}</span>
            <span className="text-[10px] font-semibold w-[78px] text-right" style={{ color: ratingColour(c.rating) }}>{cap(c.rating)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Semicircle gauge, 0 (left) → 100 (right), coloured by rating zone; score and rating as text below. */
function Gauge({ score, rating }: { score: number; rating: string | null }) {
  const cx = 70, cy = 64, r = 56;
  const pt = (s: number, rad = r) => {
    const a = Math.PI * (1 - s / 100);
    return [cx + rad * Math.cos(a), cy - rad * Math.sin(a)] as const;
  };
  const arc = (a: number, b: number) => {
    const [x1, y1] = pt(a); const [x2, y2] = pt(b);
    return `M${x1.toFixed(1)} ${y1.toFixed(1)} A${r} ${r} 0 0 1 ${x2.toFixed(1)} ${y2.toFixed(1)}`;
  };
  const s = Math.max(0, Math.min(100, score));
  const [nx, ny] = pt(s, r - 14);
  const label = rating ?? ratingOf(score);
  // Draw bands on the continuous 0–100 scale: a band covers up to its top integer + 0.5.
  const bounds = ZONES.map(([hi], i) => [i ? ZONES[i - 1][0] + 0.5 : 0, Math.min(100, hi + 0.5)] as const);
  return (
    <div className="shrink-0 flex flex-col items-center" role="img"
      aria-label={`Fear and Greed Index ${score.toFixed(0)} of 100, ${label}`}>
      <svg width={140} height={70} viewBox="0 0 140 70" aria-hidden>
        {ZONES.map(([, name, colour], i) => (
          <path key={name} d={arc(bounds[i][0] + 0.6, bounds[i][1] - 0.6)} fill="none" stroke={colour} strokeWidth={10} />
        ))}
        <line x1={cx} y1={cy} x2={nx} y2={ny} stroke="var(--ink)" strokeWidth={2.5} strokeLinecap="round" />
        <circle cx={cx} cy={cy} r={4} fill="var(--ink)" />
      </svg>
      <div className="num text-[20px] font-extrabold leading-none mt-0.5" style={{ color: "var(--ink)" }}>{score.toFixed(0)}</div>
      <div className="text-[10.5px] font-bold uppercase tracking-wide" style={{ color: ratingColour(label) }}>{cap(label)}</div>
    </div>
  );
}

const STATE: Record<VixTerm["state"], { label: string; bg: string; ink: string; hint: string }> = {
  contango: { label: "Contango", bg: "color-mix(in oklab, var(--pos) 22%, var(--surface))", ink: "var(--pos-ink)", hint: "Normal upward-sloping curve: near-term vol below 3-month vol" },
  flat: { label: "Flat", bg: "var(--surface-2)", ink: "var(--ink-2)", hint: "Curve nearly flat: rising near-term stress" },
  backwardation: { label: "Backwardation", bg: "color-mix(in oklab, var(--neg) 22%, var(--surface))", ink: "var(--neg-ink)", hint: "Inverted curve: acute near-term fear" },
};

function VixBlock({ vt }: { vt: VixTerm }) {
  const st = STATE[vt.state];
  const dRatio = vt.ratio_prev != null ? vt.ratio - vt.ratio_prev : null;
  const tiles: [string, string, string?][] = [
    ["VIX", vt.vix.toFixed(2), vt.vix9d != null ? `9D ${vt.vix9d.toFixed(2)}` : undefined],
    ["VIX3M", vt.vix3m.toFixed(2)],
    ["VIX / VIX3M", vt.ratio.toFixed(3), `${signed(dRatio, 3, "")} vs prev`],
  ];
  return (
    <div className="mt-1 border-t" style={{ borderColor: "var(--border)" }}>
      <BlockHeader label="VIX term structure" about={vt.about} sourceUrl={vt.source_url}
        right={`as of ${fmtDate(vt.asof, { month: "short", day: "numeric" })}`} />
      <div className="flex items-center gap-2 px-3 pt-1">
        <span className="text-[10px] font-extrabold uppercase px-1.5 py-0.5 rounded" title={st.hint}
          style={{ background: st.bg, color: st.ink }}>{st.label}</span>
        {vt.percentile_1y != null && (
          <span className="text-[10.5px]" style={{ color: "var(--muted)" }}>
            ratio at {ordinal(vt.percentile_1y)} percentile of the past year
          </span>
        )}
      </div>
      <dl className="grid grid-cols-3 gap-1.5 px-3 pt-1.5 pb-2.5 m-0">
        {tiles.map(([label, value, sub]) => (
          <div key={label} className="rounded border px-2 py-1" style={{ borderColor: "var(--border)" }}>
            <dt className="text-[9.5px] font-bold uppercase tracking-wide" style={{ color: "var(--ink-2)" }}>{label}</dt>
            <dd className="m-0 num text-[15px] font-bold leading-tight" style={{ color: "var(--ink)" }}>{value}</dd>
            {sub && <dd className="m-0 num text-[10px]" style={{ color: "var(--muted)" }}>{sub}</dd>}
          </div>
        ))}
      </dl>
    </div>
  );
}
