import type { ComponentType } from "react";
import { EconomicCalendar } from "./EconomicCalendar";
import { EconomicIndicators } from "./EconomicIndicators";
import { IndexSnapshot } from "./IndexSnapshot";
import { PerformancePanel } from "./PerformancePanel";
import { YieldCurvePanel } from "./YieldCurvePanel";

/**
 * Every dashboard panel is registered here. Grid placement + the
 * Customise View menu are both driven by this list.
 *   span: columns out of 12 on wide screens · tall: double-height row
 */
export interface PanelDef {
  id: string;
  title: string;
  section: "Overview" | "Equities" | "Fixed Income" | "Commodities & FX" | "Macro";
  span: 3 | 4 | 6 | 8 | 12;
  tall?: boolean;
  Component: ComponentType;
}

export const PANELS: PanelDef[] = [
  { id: "index_snapshot", title: "Index Snapshot", section: "Overview", span: 12, Component: IndexSnapshot },
  { id: "economic_indicators", title: "Economic Indicators", section: "Macro", span: 3, tall: true, Component: EconomicIndicators },
  { id: "sectors", title: "Sector Performance", section: "Equities", span: 3, Component: () => <PerformancePanel panelId="sectors" /> },
  { id: "fixed_income", title: "Fixed Income Performance", section: "Fixed Income", span: 3, tall: true, Component: () => <PerformancePanel panelId="fixed_income" showYield /> },
  { id: "yield_curve", title: "US Treasury Yield Curve", section: "Fixed Income", span: 3, Component: YieldCurvePanel },
  { id: "commodities", title: "Commodity Performance", section: "Commodities & FX", span: 3, tall: true, Component: () => <PerformancePanel panelId="commodities" /> },
  { id: "currencies", title: "Currency Performance", section: "Commodities & FX", span: 3, Component: () => <PerformancePanel panelId="currencies" /> },
  { id: "economic_calendar", title: "Upcoming Releases", section: "Macro", span: 3, Component: EconomicCalendar },
];
