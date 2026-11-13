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
