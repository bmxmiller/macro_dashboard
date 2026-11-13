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
