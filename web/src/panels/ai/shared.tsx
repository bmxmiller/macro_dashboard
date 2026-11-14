import type { ReactNode } from "react";
import { PanelMessage } from "../../components/Panel";
import { useData } from "../../lib/data";
import { relTime } from "../../lib/format";
import { useStale } from "../../lib/stale";
import type { Insights, Meta } from "../../types";

export const MISSING_MSG = "AI insights not generated yet. Add GEMINI_API_KEY / GROQ_API_KEY.";

/** insights.json + its pipeline status (stale = last run failed, note = skipped without keys). */
export function useInsights() {
  const { data, error } = useData<Insights>("insights");
  const { data: meta } = useData<Meta>("meta");
  const stale = useStale("insights");
  const sec = meta?.sections.insights;
  const note = sec?.skipped ? sec.note ?? null : null;
  return { data, error, stale, note };
}

/** Loading / missing / error states shared by the AI panels. Returns null when data is ready. */
export function InsightsState({ data, error }: { data: Insights | null; error: string | null }): ReactNode {
  if (data) return null;
  if (error) return <PanelMessage>{error.startsWith("no data yet") ? MISSING_MSG : `Could not load data: ${error}`}</PanelMessage>;
  return <PanelMessage>Loading…</PanelMessage>;
}

/** "AI · provider/model · 3h ago" plus an optional skipped-run note. */
export function AiBadge({ data, note }: { data: Insights; note: string | null }) {
  return (
    <div className="flex flex-wrap items-center gap-x-2 gap-y-1 px-3 pt-2 text-[10px]" style={{ color: "var(--muted)" }}>
      <span className="font-bold uppercase tracking-wide px-1.5 py-[1px] rounded-sm border"
        style={{ borderColor: "var(--accent)", color: "var(--ink)" }}
        title={`Written by ${data.provider}/${data.model} at ${data.generated_at}`}>
        AI · {data.provider}/{data.model} · {relTime(data.generated_at)}
      </span>
      {note && <span title={note}>Not refreshed: no LLM key set</span>}
    </div>
  );
}

export function Disclaimer({ text }: { text: string }) {
  return (
    <p className="m-0 px-3 py-2 text-[10px] italic border-t" style={{ color: "var(--muted)", borderColor: "var(--border)" }}>
      {text}
    </p>
  );
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="group-label px-3 pt-2.5 pb-1">{children}</div>;
}
