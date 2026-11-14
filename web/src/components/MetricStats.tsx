import { signed } from "../lib/format";
import type { Metric } from "../types";
import { ExternalIcon } from "./Icons";

/** Suffix for a *change* in a metric (percent-unit metrics move in percentage points). */
export function changeSuffix(units: string): string {
  if (units === "%") return "pp";
  if (units === "k" || units === "m" || units === "pp") return units;
  return "";
}

const HOSTS: [string, string][] = [
  ["fred.stlouisfed.org", "FRED"], ["ons.gov.uk", "ONS"], ["bankofengland.co.uk", "the Bank of England"],
  ["yahoo.com", "Yahoo Finance"],
];

/** "Data on FRED" / "Data on ONS"… from the data URL's host. */
function dataLinkLabel(url: string): string {
  const host = HOSTS.find(([h]) => url.includes(h));
  return host ? `Data on ${host[1]}` : "Data series";
}

/** 10y z-score / percentile and a link to the series' data page, shown in About cards. */
export function MetricStats({ metric }: { metric: Metric }) {
  return (
    <div className="space-y-1.5">
      <div className="group-label">Vs. last 10 years</div>
      <div className="flex gap-4 num" style={{ color: "var(--ink)" }}>
        <span><span style={{ color: "var(--muted)" }}>z-score </span>{signed(metric.zscore, 2, "")}</span>
        <span><span style={{ color: "var(--muted)" }}>percentile </span>
          {metric.percentile != null ? `${metric.percentile.toFixed(0)}th` : "–"}</span>
      </div>
      <a href={metric.data_url} target="_blank" rel="noopener noreferrer"
        className="inline-flex items-center gap-1 font-medium hover:underline" style={{ color: "var(--accent)" }}>
        {dataLinkLabel(metric.data_url)} <ExternalIcon />
      </a>
    </div>
  );
}
