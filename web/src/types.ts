// Mirrors pipeline/schemas.py: keep in sync.

export type Period = "1D" | "1W" | "1M" | "3M" | "6M" | "YTD" | "1Y" | "3Y";

export interface About { what: string; why: string; how_to_read: string }

export interface MarketRow {
  ticker: string;
  name: string;
  tag?: string | null;
  units?: string | null;
  price?: number | null;
  asof?: string | null;
  mode: "pct" | "diff";
  returns: Partial<Record<Period, number | null>>;
  spark: number[];
  yield_ttm?: number | null;
  duration?: number | null;
  source_url: string;
}
export interface MarketGroup { label: string; rows: MarketRow[] }
export interface MarketPanel { id: string; title: string; about: About; groups: MarketGroup[] }
export interface Markets { generated_at: string; periods: Period[]; panels: Record<string, MarketPanel> }

export interface Metric {
  id: string; group: string; name: string; units: string; decimals: number;
  good: "up" | "down" | "neutral"; frequency: string;
  value: number | null; date: string | null; period_label: string | null;
  prev: number | null; change: number | null; year_ago: number | null;
  zscore: number | null; percentile: number | null;
  history: [string, number][];
  about: About; source_url: string; data_url: string;
}
export interface Economy {
  generated_at: string;
  groups: { id: string; label: string }[];
  metrics: Metric[];
  recessions: [string, string][];
}

export interface CurvePoint { label: string; years: number; now: number | null; m1: number | null; y1: number | null }
export interface Spread { label: string; series: string; value: number; m1: number | null; history: [string, number][]; data_url: string }
export interface YieldCurve {
  generated_at: string; asof: string | null; about: About; source_url: string;
  points: CurvePoint[]; spreads: Spread[];
}

export interface CalendarEvent {
  date: string; time?: string | null; name: string; kind: "release" | "fomc" | "earnings";
  metric_id?: string | null; last_value?: string | null; last_label?: string | null;
  importance: "high" | "medium" | "low"; source_url?: string | null;
}
export interface Calendar { generated_at: string; complete: boolean; note?: string | null; events: CalendarEvent[] }

export interface Meta {
  generated_at: string;
  sections: Record<string, { ok: boolean; updated_at?: string; error?: string; failed_at?: string }>;
}

// ── UK (uk.json): same row shape as economy metrics ────────────────────────
export interface UKData {
  generated_at: string;
  groups: { id: string; label: string }[];
  metrics: Metric[];
}

// ── Positioning (positioning.json): CFTC Commitments of Traders ───────────
export interface CotMarket {
  id: string; name: string; asset_class: string;
  report: "tff" | "disaggregated"; report_name: string;
  trader_group: string; // "Leveraged funds" (TFF) | "Managed money" (Disaggregated)
  contract_code: string; exchange_name?: string | null;
  report_date: string;
  long: number; short: number; net: number;
  net_prev: number | null; change_wow: number | null;
  open_interest: number | null; net_pct_oi: number | null;
  percentile_3y: number | null; // rank of current net within trailing 3y, 0–100
  cot_index_3y: number | null;  // (net − min) / (max − min) over 3y, 0–100
  min_3y: number; max_3y: number; weeks: number;
  history: [string, number][]; // weekly net, ~3y
  about: About; source_url: string; data_url: string;
}
export interface Positioning {
  generated_at: string; report_date: string | null;
  about: About; source_url: string; markets: CotMarket[];
}

// ── Sentiment (sentiment.json) ─────────────────────────────────────────────
export interface FearGreedComponent {
  id: string; name: string; score: number | null; rating: string | null;
  value: number | null; asof: string | null; description?: string | null;
}
export interface FearGreed {
  score: number; rating: string | null; asof: string | null;
  previous_close: number | null; previous_1_week: number | null;
  previous_1_month: number | null; previous_1_year: number | null;
  history: [string, number][]; components: FearGreedComponent[];
  about: About; source_url: string;
}
export interface VixTerm {
  asof: string; vix: number; vix3m: number; vix9d?: number | null;
  ratio: number; ratio_prev: number | null; // VIX / VIX3M
  state: "contango" | "flat" | "backwardation";
  percentile_1y: number | null; history: [string, number][];
  about: About; source_url: string;
}
export interface Sentiment {
  generated_at: string;
  fear_greed: FearGreed | null; fear_greed_error?: string | null;
  vix_term: VixTerm | null; vix_term_error?: string | null;
}

// ── News (news.json) ───────────────────────────────────────────────────────
export type NewsTag = "rates" | "equities" | "fx" | "commodities" | "macro" | "central-bank" | "uk";
export interface NewsItem {
  id: string; title: string; url: string; source: string; feed: string;
  published: string; summary: string; tags: NewsTag[];
}
export interface NewsSource { id: string; source: string; url: string; ok: boolean; count: number; error?: string | null }
export interface News { generated_at: string; window_hours: number; sources: NewsSource[]; items: NewsItem[] }

// ── Earnings (earnings.json) ───────────────────────────────────────────────
export interface EarningsItem {
  ticker: string; name: string; date: string;
  time?: "BMO" | "AMC" | "DMH" | null; // before open / after close / during market hours
  eps_estimate: number | null; eps_prior_year: number | null; prior_year_date: string | null;
  source_url: string;
}
export interface Earnings {
  generated_at: string; window_days: number; universe_size: number;
  failed: string[]; about: About; items: EarningsItem[];
}
