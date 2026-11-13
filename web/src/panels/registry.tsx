import type { ComponentType } from "react";
import { Panel, PanelMessage } from "../components/Panel";
import { PerformancePanel } from "./PerformancePanel";

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

function Stub({ id, title }: { id: string; title: string }) {
  return (
    <Panel id={id} title={title}>
      <PanelMessage>Coming soon.</PanelMessage>
    </Panel>
  );
}
const stub = (id: string, title: string) => () => <Stub id={id} title={title} />;

export const PANELS: PanelDef[] = [
  { id: "index_snapshot", title: "Index Snapshot", section: "Overview", span: 12, Component: stub("index_snapshot", "Index Snapshot") },
  { id: "economic_indicators", title: "Economic Indicators", section: "Macro", span: 3, tall: true, Component: stub("economic_indicators", "Economic Indicators") },
  { id: "sectors", title: "Sector Performance", section: "Equities", span: 3, Component: () => <PerformancePanel panelId="sectors" /> },
  { id: "fixed_income", title: "Fixed Income Performance", section: "Fixed Income", span: 3, tall: true, Component: () => <PerformancePanel panelId="fixed_income" showYield /> },
  { id: "yield_curve", title: "US Treasury Yield Curve", section: "Fixed Income", span: 3, Component: stub("yield_curve", "US Treasury Yield Curve") },
  { id: "commodities", title: "Commodity Performance", section: "Commodities & FX", span: 3, tall: true, Component: () => <PerformancePanel panelId="commodities" /> },
  { id: "currencies", title: "Currency Performance", section: "Commodities & FX", span: 3, Component: () => <PerformancePanel panelId="currencies" /> },
  { id: "economic_calendar", title: "Upcoming Releases", section: "Macro", span: 3, Component: stub("economic_calendar", "Upcoming Releases") },
];
