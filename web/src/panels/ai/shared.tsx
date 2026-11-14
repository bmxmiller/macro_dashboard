import type { ReactNode } from "react";
import { ExternalIcon } from "../../components/Icons";
import { PanelMessage } from "../../components/Panel";
import { useData } from "../../lib/data";
import { relTime } from "../../lib/format";
import { useStale } from "../../lib/stale";
import type { Insights, Meta, SourceLink } from "../../types";

export const MISSING_MSG = "AI insights not generated yet. Add GEMINI_API_KEY / GROQ_API_KEY.";

/** insights.json + its pipeline status (stale = last run failed, note = skipped without keys). */
export function useInsights() {
  const { data, error } = useData<Insights>("insights");
  const { data: meta } = useData<Meta>("meta");
  const stale = useStale("insights");
  const sec = meta?.sections.insights;
  const note = sec?.skipped ? sec.note ?? null : null;
  const missing = !data && !!error && error.startsWith("no data yet");
  return { data, error: missing ? null : error, missing, stale, note };
}

/** Loading / missing / error states. Returns null when data is ready. */
export function LoadState({ ready, error, missing, missingMsg }: {
  ready: boolean; error: string | null; missing: boolean; missingMsg: string;
}): ReactNode {
  if (ready) return null;
  if (missing) return <PanelMessage>{missingMsg}</PanelMessage>;
  if (error) return <PanelMessage>Could not load data: {error}</PanelMessage>;
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

/** "Data as of 14 Nov 2026, 07:59 UTC" from an ISO timestamp. */
export function DataAsOf({ iso }: { iso: string | null | undefined }) {
  if (!iso) return null;
  const d = new Date(iso);
  const txt = d.toLocaleString("en-GB", {
    day: "numeric", month: "short", year: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC",
  });
  return <div className="px-3 pt-1 text-[10px]" style={{ color: "var(--muted)" }}>Data as of {txt} UTC</div>;
}

/** Source links for the About popover (Panel `aboutExtra`). */
export function SourceList({ sources, methodologyUrl }: { sources: SourceLink[]; methodologyUrl?: string }) {
  return (
    <div className="mt-2 text-[11px]">
      <div className="font-bold mb-0.5" style={{ color: "var(--ink)" }}>Sources</div>
      <ul className="m-0 pl-4 space-y-0.5">
        {sources.map((s, i) => (
          <li key={i}>
            <a href={s.url} target="_blank" rel="noopener noreferrer" className="hover:underline inline-flex items-center gap-1"
              style={{ color: "var(--ink-2)" }}>{s.label} <ExternalIcon /></a>
          </li>
        ))}
        {methodologyUrl && (
          <li>
            <a href={methodologyUrl} target="_blank" rel="noopener noreferrer" className="hover:underline inline-flex items-center gap-1"
              style={{ color: "var(--ink-2)" }}>Methodology (code and rules) <ExternalIcon /></a>
          </li>
        )}
      </ul>
    </div>
  );
}

export function Disclaimer({ text }: { text: string }) {
  return <p className="m-0 px-3 pt-1 pb-2 text-[10px] italic" style={{ color: "var(--muted)" }}>{text}</p>;
}

export function SectionLabel({ children }: { children: ReactNode }) {
  return <div className="group-label px-3 pt-2.5 pb-1">{children}</div>;
}
