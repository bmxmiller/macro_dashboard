"""Output contracts. Every JSON file the frontend reads is validated against these."""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field


class About(BaseModel):
    what: str
    why: str
    how_to_read: str


class MarketRow(BaseModel):
    ticker: str
    name: str
    tag: Optional[str] = None
    units: Optional[str] = None
    price: Optional[float] = None
    asof: Optional[str] = None
    mode: Literal["pct", "diff"] = "pct"
    returns: dict[str, Optional[float]]
    spark: list[float] = Field(default_factory=list)
    yield_ttm: Optional[float] = None
    duration: Optional[float] = None
    source_url: str


class MarketGroup(BaseModel):
    label: str
    rows: list[MarketRow]


class MarketPanel(BaseModel):
    id: str
    title: str
    about: About
    groups: list[MarketGroup]


class Markets(BaseModel):
    generated_at: str
    periods: list[str]
    panels: dict[str, MarketPanel]


class Metric(BaseModel):
    id: str
    group: str
    name: str
    units: str
    decimals: int
    good: Literal["up", "down", "neutral"]
    frequency: str
    value: Optional[float]
    date: Optional[str]
    period_label: Optional[str]
    prev: Optional[float]
    change: Optional[float]
    year_ago: Optional[float]
    zscore: Optional[float]
    percentile: Optional[float]
    history: list[list]
    about: About
    source_url: str
    data_url: str


class Economy(BaseModel):
    generated_at: str
    groups: list[dict]
    metrics: list[Metric]
    recessions: list[list[str]]


class CurvePoint(BaseModel):
    label: str
    years: float
    now: Optional[float]
    m1: Optional[float]
    y1: Optional[float]


class YieldCurve(BaseModel):
    generated_at: str
    asof: Optional[str]
    about: About
    source_url: str
    points: list[CurvePoint]
    spreads: list[dict]


class CalendarEvent(BaseModel):
    date: str
    time: Optional[str] = None
    name: str
    kind: Literal["release", "fomc", "earnings"]
    metric_id: Optional[str] = None
    last_value: Optional[str] = None
    last_label: Optional[str] = None
    importance: Literal["high", "medium", "low"] = "medium"
    source_url: Optional[str] = None


class Calendar(BaseModel):
    generated_at: str
    complete: bool
    note: Optional[str] = None
    events: list[CalendarEvent]


# ── UK ─────────────────────────────────────────────────────────────────────

class UK(BaseModel):
    generated_at: str
    groups: list[dict]
    metrics: list[Metric]  # same row shape as economy metrics


# ── Positioning (CFTC COT) ─────────────────────────────────────────────────

class CotMarket(BaseModel):
    id: str
    name: str
    asset_class: str
    report: Literal["tff", "disaggregated"]
    report_name: str
    trader_group: str              # "Leveraged funds" | "Managed money"
    contract_code: str
    exchange_name: Optional[str] = None
    report_date: str
    long: int
    short: int
    net: int
    net_prev: Optional[int]
    change_wow: Optional[int]
    open_interest: Optional[int]
    net_pct_oi: Optional[float]
    percentile_3y: Optional[float]  # rank of current net within trailing 3y (0–100)
    cot_index_3y: Optional[float]   # (net − min) / (max − min) over 3y (0–100)
    min_3y: int
    max_3y: int
    weeks: int
    history: list[list]             # [[date, net], ...] weekly, ~3y
    about: About
    source_url: str
    data_url: str


class Positioning(BaseModel):
    generated_at: str
    report_date: Optional[str]
    about: About
    source_url: str
    markets: list[CotMarket]


# ── Sentiment ──────────────────────────────────────────────────────────────

class FearGreedComponent(BaseModel):
    id: str
    name: str
    score: Optional[float]
    rating: Optional[str]
    value: Optional[float]
    asof: Optional[str]
    description: Optional[str] = None


class FearGreed(BaseModel):
    score: float
    rating: Optional[str]
    asof: Optional[str]
    previous_close: Optional[float]
    previous_1_week: Optional[float]
    previous_1_month: Optional[float]
    previous_1_year: Optional[float]
    history: list[list]             # [[date, score], ...] ~1y daily
    components: list[FearGreedComponent]
    about: About
    source_url: str


class VixTerm(BaseModel):
    asof: str
    vix: float
    vix3m: float
    vix9d: Optional[float] = None
    ratio: float                    # VIX / VIX3M
    ratio_prev: Optional[float]
    state: Literal["contango", "flat", "backwardation"]
    percentile_1y: Optional[float]
    history: list[list]             # [[date, ratio], ...] ~1y daily
    about: About
    source_url: str


class Sentiment(BaseModel):
    generated_at: str
    fear_greed: Optional[FearGreed]
    fear_greed_error: Optional[str] = None
    vix_term: Optional[VixTerm]
    vix_term_error: Optional[str] = None


# ── News ───────────────────────────────────────────────────────────────────

NewsTag = Literal["rates", "equities", "fx", "commodities", "macro", "central-bank", "uk"]


class NewsItem(BaseModel):
    id: str
    title: str
    url: str
    source: str
    feed: str
    published: str
    summary: str
    tags: list[NewsTag]


class NewsSource(BaseModel):
    id: str
    source: str
    url: str
    ok: bool
    count: int                      # items inside the window, before dedupe/caps
    error: Optional[str] = None


class News(BaseModel):
    generated_at: str
    window_hours: int
    sources: list[NewsSource]
    items: list[NewsItem]


# ── Earnings ───────────────────────────────────────────────────────────────

class EarningsItem(BaseModel):
    ticker: str
    name: str
    date: str
    time: Optional[Literal["BMO", "AMC", "DMH"]] = None  # before open / after close / during hours
    eps_estimate: Optional[float]
    eps_prior_year: Optional[float]
    prior_year_date: Optional[str]
    source_url: str


class Earnings(BaseModel):
    generated_at: str
    window_days: int
    universe_size: int
    failed: list[str]
    about: About
    items: list[EarningsItem]


# ── S&P 500 heat map (sp500.json) ──────────────────────────────────────────

class SP500Row(BaseModel):
    t: str
    name: str
    sector: str
    price: float
    shares: int            # cached between runs (refreshed weekly); cap = shares x price
    cap: float             # market cap, US$ billions
    returns: dict[str, Optional[float]]   # PRICE returns, %


class SP500(BaseModel):
    generated_at: str
    asof: str
    periods: list[str]
    source_url: str
    about: About
    failed: list[str]
    rows: list[SP500Row]


# ── Macro regime (regime.json) ─────────────────────────────────────────────
# Computed by code only (pipeline/ai/regime.py); needs no LLM key.

class RegimeComponent(BaseModel):
    id: str
    metric: str
    label: str
    value: Optional[float]
    units: str
    score: Optional[float]
    asof: Optional[str] = None
    detail: dict[str, Optional[float]]


class RegimeSignal(BaseModel):
    score: Optional[float]          # −1..1
    direction: Optional[Literal["up", "down"]]
    state: Optional[Literal["accelerating", "decelerating", "flat"]]
    components: list[RegimeComponent]


Quadrant = Literal["Inflationary boom", "Goldilocks", "Stagflation", "Disinflationary slowdown"]


class GrowthInflation(BaseModel):
    quadrant: Optional[Quadrant]
    label: Optional[str]            # e.g. "Goldilocks / Inflationary boom boundary"
    boundary: bool
    allowed_quadrants: list[Quadrant]
    growth: RegimeSignal
    inflation: RegimeSignal
    level_note: Optional[str]
    core_pce_pct: Optional[float]
    inflation_target_pct: float


class GrowthPolicy(BaseModel):
    label: Optional[str]
    stance: Optional[Literal["restrictive", "neutral", "accommodative"]]
    borderline: bool
    real_rate_pct: Optional[float]
    fed_funds_upper_pct: Optional[float] = None
    fed_funds_mid_pct: Optional[float] = None
    core_pce_pct: Optional[float] = None
    neutral_band_pct: list[float]
    growth_direction: Optional[Literal["up", "down"]]
    note: str


class CreditPair(BaseModel):
    long: str
    short: str
    long_ret_pct: float
    short_ret_pct: float
    spread_pp: float


class CreditDuration(BaseModel):
    label: Optional[str]
    leader: Optional[Literal["credit", "duration", "balanced"]]
    borderline: bool
    score_pp: Optional[float]
    period: str
    pairs: list[CreditPair]
    hy_oas_3m_chg_bp: Optional[int]
    hy_oas_confirms: Optional[bool]


class Tendency(BaseModel):
    id: str
    text: str


class RegimeTendencies(BaseModel):
    quadrant: Optional[Quadrant]
    items: list[Tendency]
    basis: str


class Regime(BaseModel):
    generated_at: str
    data_asof: Optional[str]
    about: About
    methodology_url: str
    sources: list[dict[str, str]]   # [{label, url}]
    growth_inflation: GrowthInflation
    growth_policy: GrowthPolicy
    credit_duration: CreditDuration
    tendencies: RegimeTendencies
    stale_inputs: list[str]


# ── AI insights (insights.json) ────────────────────────────────────────────
# LLM text only, after validation. The regime itself lives in regime.json.

class InsightsBrief(BaseModel):
    headline: str
    bullets: list[str]
    what_moved: str
    cycle_view: str


class InsightsNewsLink(BaseModel):
    id: str
    title: str
    url: str
    source: str


class InsightsNewsCluster(BaseModel):
    topic: str
    summary: str
    tags: list[str]
    item_ids: list[str]
    items: list[InsightsNewsLink]   # resolved at build time so links survive news.json updates


class RegimeExplainer(BaseModel):
    rationale: str
    caveats: list[str]
    regime_generated_at: Optional[str]  # the regime.json this text explains
    regime_label: Optional[str]


class Insights(BaseModel):
    generated_at: str
    provider: str
    model: str
    data_asof: Optional[str]
    about: About
    sources: list[dict[str, str]]
    brief: InsightsBrief
    news_clusters: list[InsightsNewsCluster]
    regime_explainer: RegimeExplainer
    disclaimer: str
