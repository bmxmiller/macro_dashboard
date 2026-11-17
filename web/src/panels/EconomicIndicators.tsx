import { MetricList } from "../components/MetricList";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { useStale } from "../lib/stale";
import type { About, Economy } from "../types";

const ABOUT: About = {
  what: "Headline US macro data across inflation, the labour market, activity, the consumer, policy and credit, pulled from FRED and the original statistical agencies.",
  why: "These releases drive Fed expectations, bond yields and the earnings outlook. Seeing them side by side shows whether the economy is heating up or cooling down.",
  how_to_read: "The arrow compares the latest print with the previous one. Green means the move is benign for the economy and red means it is not (grey: no clear good direction). It is not an investment signal. Click a row for its full history with recessions shaded, or ⓘ for what the metric means.",
};

/** Grouped list of US macro metrics; each row opens its history chart. */
export function EconomicIndicators() {
  const { data, error } = useData<Economy>("economy");
  const stale = useStale("economy");

  return (
    <Panel id="economic_indicators" title="Economic Indicators" subtitle="Latest print vs. previous"
      about={ABOUT} sourceUrl="https://fred.stlouisfed.org/" stale={stale} updatedSection="economy">
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && <MetricList groups={data.groups} metrics={data.metrics} recessions={data.recessions} />}
    </Panel>
  );
}
