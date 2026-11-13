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
