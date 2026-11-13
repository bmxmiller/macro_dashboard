import { Panel, PanelMessage } from "../components/Panel";
import { useData } from "../lib/data";
import { fmtDate } from "../lib/format";
import { useStale } from "../lib/stale";
import type { About, Calendar, CalendarEvent } from "../types";

const ABOUT: About = {
  what: "Scheduled US data releases and Federal Reserve (FOMC) decisions for the coming weeks, with the last reading of each.",
  why: "Markets move most around scheduled releases: a surprise in CPI, payrolls or the Fed's decision can reprice rates and equities in minutes.",
  how_to_read: "Red dots mark high-importance events, which usually move markets the most. Compare the next print with the last value shown on the right. Times are US Eastern.",
};

const IMPORTANCE: Record<CalendarEvent["importance"], { colour: string; label: string }> = {
  high: { colour: "var(--neg)", label: "High importance" },
  medium: { colour: "var(--accent)", label: "Medium importance" },
  low: { colour: "var(--muted)", label: "Low importance" },
};

const iso = (d: Date) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;

/** "Today" / "Tomorrow" / "This week" relative to the viewer's local date (weeks end on Sunday). */
function relLabel(date: string, now = new Date()): string | null {
  const today = iso(now);
  if (date === today) return "Today";
  const tmr = new Date(now); tmr.setDate(now.getDate() + 1);
  if (date === iso(tmr)) return "Tomorrow";
  const sunday = new Date(now); sunday.setDate(now.getDate() + ((7 - now.getDay()) % 7));
  return date > today && date <= iso(sunday) ? "This week" : null;
}

/** Upcoming releases and FOMC meetings. */
export function EconomicCalendar() {
  const { data, error } = useData<Calendar>("calendar");
  const stale = useStale("calendar");
  const fomcUrl = data?.events.find((e) => e.kind === "fomc")?.source_url ?? undefined;

  return (
    <Panel id="economic_calendar" title="Upcoming Releases" subtitle="US data & Fed · ET"
      about={ABOUT} sourceUrl={fomcUrl} stale={stale}>
      {error && <PanelMessage>Could not load data: {error}</PanelMessage>}
      {!data && !error && <PanelMessage>Loading…</PanelMessage>}
      {data?.note && (
        <div className="px-3 py-1.5 text-[10.5px] border-b" style={{ color: "var(--muted)", borderColor: "var(--border)" }}>
          {data.note}
        </div>
      )}
      {data && data.events.length === 0 && <PanelMessage>No upcoming events.</PanelMessage>}
      {data && data.events.length > 0 && (
        <ul className="m-0 p-0 list-none">
          {data.events.map((e) => <EventRow key={`${e.date}-${e.name}`} event={e} />)}
        </ul>
      )}
    </Panel>
  );
}

function EventRow({ event: e }: { event: CalendarEvent }) {
  const imp = IMPORTANCE[e.importance];
  const rel = relLabel(e.date);
  return (
    <li className="flex items-center gap-2 px-3 py-1.5 border-t first:border-t-0" style={{ borderColor: "var(--border)" }}>
      <span role="img" aria-label={imp.label} title={imp.label}
        className="inline-block w-2 h-2 rounded-full shrink-0" style={{ background: imp.colour }} />
      <div className="min-w-0 flex-1">
        {e.source_url ? (
          <a href={e.source_url} target="_blank" rel="noopener noreferrer"
            className="block font-semibold truncate hover:underline" style={{ color: "var(--ink)" }}>{e.name}</a>
        ) : (
          <div className="font-semibold truncate" style={{ color: "var(--ink)" }}>{e.name}</div>
        )}
        <div className="text-[10px] num flex items-center gap-1.5" style={{ color: "var(--muted)" }}>
          {rel && (
            <span className="font-bold uppercase text-[9px] px-1 rounded-sm"
              style={{ background: "var(--accent)", color: "var(--accent-ink)" }}>{rel}</span>
          )}
          <span>{fmtDate(e.date, { weekday: "short", month: "short", day: "numeric" })}{e.time ? ` · ${e.time}` : ""}</span>
        </div>
      </div>
      {e.last_value && (
        <div className="text-right shrink-0">
          <div className="num font-bold" style={{ color: "var(--ink)" }}>{e.last_value}</div>
          {e.last_label && <div className="text-[9px] uppercase tracking-wide" style={{ color: "var(--muted)" }}>Last · {e.last_label}</div>}
        </div>
      )}
    </li>
  );
}
