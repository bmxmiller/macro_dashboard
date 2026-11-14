import type { ComponentType } from "react";
import { MacroBrief } from "./ai/MacroBrief";
import { RegimePanel } from "./ai/RegimePanel";
import { EarningsCalendar } from "./EarningsCalendar";
import { EconomicCalendar } from "./EconomicCalendar";
import { EconomicIndicators } from "./EconomicIndicators";
import { IndexSnapshot } from "./IndexSnapshot";
import { NewsFeed } from "./NewsFeed";
import { PerformancePanel } from "./PerformancePanel";
import { Positioning } from "./Positioning";
import { Sentiment } from "./Sentiment";
import { UkMacro } from "./UkMacro";
import { YieldCurvePanel } from "./YieldCurvePanel";

/**
 * Every dashboard panel is registered here. Grid placement + the
 * Customise View menu are both driven by this list.
 *   span: columns out of 12 on wide screens · tall: double-height row
 */
export const SECTIONS = [
  "Overview", "AI Insights", "Equities", "Fixed Income", "Commodities & FX", "Macro", "Sentiment & Positioning", "News",
] as const;

export interface PanelDef {
  id: string;
  title: string;
  section: (typeof SECTIONS)[number];
  span: 3 | 4 | 6 | 8 | 12;
  tall?: boolean;
  Component: ComponentType;
}

export const PANELS: PanelDef[] = [
  { id: "index_snapshot", title: "Index Snapshot", section: "Overview", span: 12, Component: IndexSnapshot },
  { id: "macro_brief", title: "AI Macro Brief", section: "AI Insights", span: 6, tall: true, Component: MacroBrief },
  { id: "macro_regime", title: "Macro Regime", section: "AI Insights", span: 6, tall: true, Component: RegimePanel },
  { id: "economic_indicators", title: "Economic Indicators", section: "Macro", span: 3, tall: true, Component: EconomicIndicators },
  { id: "sectors", title: "Sector Performance", section: "Equities", span: 3, Component: () => <PerformancePanel panelId="sectors" /> },
  { id: "earnings_calendar", title: "Earnings Calendar", section: "Equities", span: 3, Component: EarningsCalendar },
  { id: "fixed_income", title: "Fixed Income Performance", section: "Fixed Income", span: 3, tall: true, Component: () => <PerformancePanel panelId="fixed_income" showYield /> },
  { id: "yield_curve", title: "US Treasury Yield Curve", section: "Fixed Income", span: 3, Component: YieldCurvePanel },
  { id: "commodities", title: "Commodity Performance", section: "Commodities & FX", span: 3, tall: true, Component: () => <PerformancePanel panelId="commodities" /> },
  { id: "currencies", title: "Currency Performance", section: "Commodities & FX", span: 3, Component: () => <PerformancePanel panelId="currencies" /> },
  { id: "economic_calendar", title: "Upcoming Releases", section: "Macro", span: 3, Component: EconomicCalendar },
  { id: "uk_macro", title: "UK Macro", section: "Macro", span: 3, Component: UkMacro },
  { id: "sentiment", title: "Market Sentiment", section: "Sentiment & Positioning", span: 3, Component: Sentiment },
  { id: "positioning", title: "Futures Positioning", section: "Sentiment & Positioning", span: 3, Component: Positioning },
  { id: "news", title: "Market News", section: "News", span: 3, tall: true, Component: NewsFeed },
];
