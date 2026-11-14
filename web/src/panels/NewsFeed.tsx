import { useMemo, useState } from "react";
import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { relTime, safeUrl } from "../lib/format";
import { useStale } from "../lib/stale";
import type { About, News, NewsItem, NewsSource, NewsTag } from "../types";

const ABOUT: About = {
  what: "Recent market and economic headlines from free RSS feeds: central banks and statistical agencies first, then financial news outlets. Each item is tagged by topic with simple keyword rules.",
  why: "Headlines explain why prices moved and flag policy announcements and data releases as they happen, alongside the numbers elsewhere on the dashboard.",
  how_to_read: "Use the chips to filter by topic (pick several to combine them; All clears the filter). Titles link to the original article in a new tab. Times are relative to now. Feed health (below) shows which sources answered on the last update.",
};

const TAG_ORDER: NewsTag[] = ["macro", "central-bank", "rates", "equities", "fx", "commodities", "uk"];
const TAG_LABEL: Record<NewsTag, string> = {
  macro: "Macro", "central-bank": "Central banks", rates: "Rates", equities: "Equities",
  fx: "FX", commodities: "Commodities", uk: "UK",
};

/** Filterable headline list with feed health in the About card. */
export function NewsFeed() {
  const { data, error } = useData<News>("news");
  const stale = useStale("news");
  const [selected, setSelected] = useState<NewsTag[]>([]);

  const tags = useMemo(() => {
    const present = new Set(data?.items.flatMap((i) => i.tags) ?? []);
    return TAG_ORDER.filter((t) => present.has(t));
  }, [data]);
  const items = useMemo(() => {
    const all = data?.items ?? [];
    if (!selected.length) return all;
    return all.filter((i) => i.tags.some((t) => selected.includes(t)));
  }, [data, selected]);

  const toggle = (t: NewsTag) => setSelected((s) => (s.includes(t) ? s.filter((x) => x !== t) : [...s, t]));

  return (
    <Panel id="news" title="Market News" subtitle={data ? `Last ${data.window_hours}h · ${data.items.length} headlines` : undefined}
      about={ABOUT} aboutExtra={data && <FeedHealth sources={data.sources} />} stale={stale}
      headerRight={data && <FeedHealthBadge sources={data.sources} />}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data && (
        <>
          <div role="group" aria-label="Filter news by topic"
            className="flex flex-wrap gap-1 px-3 py-2 sticky top-0 z-[1] border-b"
            style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
            <Chip active={!selected.length} onClick={() => setSelected([])}>All</Chip>
            {tags.map((t) => <Chip key={t} active={selected.includes(t)} onClick={() => toggle(t)}>{TAG_LABEL[t]}</Chip>)}
          </div>
          {items.length === 0 && <PanelMessage>No headlines match this filter.</PanelMessage>}
          <ul className="m-0 p-0 list-none">
            {items.map((i) => <NewsRow key={i.id} item={i} />)}
          </ul>
        </>
      )}
    </Panel>
  );
}

function Chip({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" aria-pressed={active} onClick={onClick}
      className="px-2 py-0.5 rounded-full text-[10.5px] font-bold border"
      style={active
        ? { background: "var(--accent)", color: "var(--accent-ink)", borderColor: "var(--accent)" }
        : { color: "var(--ink-2)", borderColor: "var(--border)" }}>
      {children}
    </button>
  );
}

function NewsRow({ item: i }: { item: NewsItem }) {
  const href = safeUrl(i.url);
  return (
    <li className="px-3 py-1.5 border-t first:border-t-0" style={{ borderColor: "var(--border)" }}>
      {href ? (
        <a href={href} target="_blank" rel="noopener noreferrer"
          className="font-semibold leading-snug line-clamp-2 hover:underline" style={{ color: "var(--ink)" }}>
          {i.title}
        </a>
      ) : (
        <span className="font-semibold leading-snug line-clamp-2" style={{ color: "var(--ink)" }}>{i.title}</span>
      )}
      <div className="flex items-center gap-1.5 mt-0.5 text-[10px]" style={{ color: "var(--muted)" }}>
        <span className="font-semibold" style={{ color: "var(--ink-2)" }}>{i.source}</span>
        <span aria-hidden>·</span>
        <time dateTime={i.published} title={new Date(i.published).toLocaleString()}>{relTime(i.published)}</time>
        {i.tags.length > 0 && <>
          <span aria-hidden>·</span>
          <span className="truncate">{i.tags.map((t) => TAG_LABEL[t] ?? t).join(", ")}</span>
        </>}
      </div>
      {i.summary && <p className="m-0 mt-0.5 text-[11px] line-clamp-1" style={{ color: "var(--ink-2)" }}>{i.summary}</p>}
    </li>
  );
}

/** "12/15 feeds" in the header, so failures are visible without opening ⓘ. */
function FeedHealthBadge({ sources }: { sources: NewsSource[] }) {
  const ok = sources.filter((s) => s.ok).length;
  return (
    <span className="text-[9px] font-bold uppercase whitespace-nowrap opacity-75"
      title={`${ok} of ${sources.length} feeds answered on the last update`}>
      {ok}/{sources.length} feeds
    </span>
  );
}

/** Per-feed status list (ok / item count / error), shown in the panel's About card. */
function FeedHealth({ sources }: { sources: NewsSource[] }) {
  return (
    <div className="text-[11px]">
      <div className="group-label mb-0.5">Feed health</div>
      <ul className="m-0 p-0 list-none space-y-0.5">
        {sources.map((s) => (
          <li key={s.id} className="flex gap-1.5">
            <span className="font-bold w-[34px] shrink-0" style={{ color: s.ok ? "var(--pos-ink)" : "var(--neg-ink)" }}>
              {s.ok ? "OK" : "Fail"}
            </span>
            <span className="min-w-0">
              <span style={{ color: "var(--ink)" }}>{s.source}</span>{" "}
              <span className="mono" style={{ color: "var(--muted)" }}>({s.id})</span>
              {s.ok
                ? <span className="num" style={{ color: "var(--muted)" }}> · {s.count} items</span>
                : <span className="block break-words" style={{ color: "var(--muted)" }}>{s.error ?? "failed"}</span>}
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}
