import type { Metric } from "../types";

/** The metric as shown in the chosen view: with `alt` selected its fields overlay the primary ones. */
export function metricView(m: Metric, useAlt: boolean): Metric {
  if (!useAlt || !m.alt) return m;
  const { label, primary_label, ...a } = m.alt;
  // The About text describes the primary view; say so, so YoY thresholds are not read against a MoM print.
  const about = { ...m.about, how_to_read: `You are viewing the ${label} version of this series. The thresholds and examples below describe the ${primary_label} version. ${m.about.how_to_read}` };
  return { ...m, ...a, about };
}

/** Small YoY | MoM segmented control, shown only for metrics that have an alternative view. */
export function ViewToggle({ metric, useAlt, onChange }: {
  metric: Metric; useAlt: boolean; onChange: (alt: boolean) => void;
}) {
  if (!metric.alt) return null;
  const opts: [string, boolean][] = [[metric.alt.primary_label, false], [metric.alt.label, true]];
  return (
    <div role="group" aria-label={`${metric.name} view`} className="inline-flex rounded border overflow-hidden"
      style={{ borderColor: "var(--border)" }} onClick={(e) => e.stopPropagation()}>
      {opts.map(([label, alt]) => (
        <button key={label} type="button" aria-pressed={useAlt === alt} onClick={() => onChange(alt)}
          className="px-1.5 py-[1px] text-[9.5px] font-bold"
          style={useAlt === alt
            ? { background: "var(--accent)", color: "var(--accent-ink)" }
            : { color: "var(--ink-2)" }}>
          {label}
        </button>
      ))}
    </div>
  );
}
