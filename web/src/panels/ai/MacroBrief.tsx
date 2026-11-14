import { ExternalIcon } from "../../components/Icons";
import { Panel } from "../../components/Panel";
import type { About } from "../../types";
import { AiBadge, DataAsOf, Disclaimer, LoadState, MISSING_MSG, SectionLabel, SourceList, useInsights } from "./shared";

const FALLBACK_ABOUT: About = {
  what: "A short, AI-written summary of today's dashboard data and clustered news headlines.",
  why: "It turns dozens of panels into a two-minute read.",
  how_to_read: "Written by a free LLM from a digest of the published numbers; an automatic fact check verifies every number, unit, direction and label before it is published. Not investment advice.",
};

/** AI macro brief: headline, bullets, what moved, cycle view and news clusters. */
export function MacroBrief() {
  const { data, error, missing, stale, note } = useInsights();

  return (
    <Panel id="macro_brief" title="AI Macro Brief" subtitle="Daily summary · AI-generated"
      about={data?.about ?? FALLBACK_ABOUT}
      aboutExtra={data ? <SourceList sources={data.sources} /> : undefined} stale={stale}>
      <LoadState ready={!!data} error={error} missing={missing} missingMsg={MISSING_MSG} />
      {data && (
        <>
          <AiBadge data={data} note={note} />
          <DataAsOf iso={data.data_asof} />
          <h3 className="m-0 px-3 pt-2 text-[14px] font-extrabold leading-snug" style={{ color: "var(--ink)" }}>
            {data.brief.headline}
          </h3>
          <ul className="m-0 mt-1.5 pl-7 pr-3 space-y-1 text-[12px] leading-snug" style={{ color: "var(--ink)" }}>
            {data.brief.bullets.map((b, i) => <li key={i}>{b}</li>)}
          </ul>

          <SectionLabel>What moved</SectionLabel>
          <p className="m-0 px-3 text-[12px] leading-snug" style={{ color: "var(--ink-2)" }}>{data.brief.what_moved}</p>

          <SectionLabel>Cycle view</SectionLabel>
          <p className="m-0 px-3 text-[12px] leading-snug" style={{ color: "var(--ink-2)" }}>{data.brief.cycle_view}</p>

          {data.news_clusters.length > 0 && (
            <>
              <SectionLabel>News themes</SectionLabel>
              <ul className="m-0 p-0 list-none">
                {data.news_clusters.map((c, ci) => (
                  <li key={`${ci}-${c.topic}`} className="px-3 py-2 border-t" style={{ borderColor: "var(--border)" }}>
                    <div className="flex flex-wrap items-baseline gap-1.5">
                      <span className="font-bold text-[12px]" style={{ color: "var(--ink)" }}>{c.topic}</span>
                      {c.tags.map((t, ti) => (
                        <span key={ti} className="text-[9.5px] font-semibold uppercase px-1 rounded-sm"
                          style={{ background: "var(--surface-2)", color: "var(--muted)" }}>{t}</span>
                      ))}
                    </div>
                    <p className="m-0 mt-0.5 text-[11.5px] leading-snug" style={{ color: "var(--ink-2)" }}>{c.summary}</p>
                    <ul className="m-0 mt-1 p-0 list-none space-y-0.5">
                      {c.items.map((it) => (
                        <li key={it.id} className="text-[11px] leading-snug">
                          <a href={it.url} target="_blank" rel="noopener noreferrer"
                            className="group inline-flex items-baseline gap-1 hover:underline" style={{ color: "var(--ink)" }}>
                            <span>{it.title}</span>
                            <span className="text-[9.5px] uppercase shrink-0" style={{ color: "var(--muted)" }}>{it.source}</span>
                            <span className="opacity-0 group-hover:opacity-100 shrink-0" style={{ color: "var(--muted)" }}><ExternalIcon /></span>
                          </a>
                        </li>
                      ))}
                    </ul>
                  </li>
                ))}
              </ul>
            </>
          )}
          <div className="border-t mt-1" style={{ borderColor: "var(--border)" }}><Disclaimer text={data.disclaimer} /></div>
        </>
      )}
    </Panel>
  );
}
