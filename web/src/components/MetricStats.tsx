import { signed } from "../lib/format";
import type { Metric } from "../types";
import { ExternalIcon } from "./Icons";

/** Suffix for a *change* in a metric (percent-unit metrics move in percentage points). */
export function changeSuffix(units: string): string {
  if (units === "%") return "pp";
  if (units === "k" || units === "m" || units === "pp") return units;
  return "";
}

/** 10y z-score / percentile and a link to the FRED data page, shown in About cards. */
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
        Data on FRED <ExternalIcon />
      </a>
    </div>
  );
}
