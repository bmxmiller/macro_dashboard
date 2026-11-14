import { MetricList } from "../components/MetricList";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { useStale } from "../lib/stale";
import type { About, UKData } from "../types";

const ABOUT: About = {
  what: "Core UK macro data: CPI inflation, the labour market, GDP growth, Bank Rate, gilt yields and sterling, from the Office for National Statistics (ONS) and the Bank of England.",
  why: "The Bank of England's Monetary Policy Committee (MPC) sets Bank Rate to bring CPI inflation back to the government's 2% target. These prints drive MPC expectations, gilt yields and the pound.",
  how_to_read: "Compare CPI with the 2% target: well above it argues for higher or longer-held rates, below it for cuts. The arrow compares the latest print with the previous one (green benign, red not, grey no clear good direction). Click a row for its full history, or ⓘ for what each metric means.",
};

/** UK macro metrics, same row format as the US Economic Indicators. */
export function UkMacro() {
  const { data, error } = useData<UKData>("uk");
  const stale = useStale("uk");

  return (
    <Panel id="uk_macro" title="UK Macro" subtitle="ONS & Bank of England · latest vs. previous"
      about={ABOUT} sourceUrl="https://www.ons.gov.uk/economy" stale={stale}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && data.metrics.length === 0 && <PanelMessage>No UK data available.</PanelMessage>}
      {data && <MetricList groups={data.groups} metrics={data.metrics} />}
    </Panel>
  );
}
