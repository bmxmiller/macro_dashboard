import { APP_NAME } from "../config";
import { useData } from "../lib/data";
import { relTime } from "../lib/format";
import { PANELS, SECTIONS } from "../panels/registry";
import { useSettings } from "../state/store";
import type { Meta, Period } from "../types";
import { LogoMark, MoonIcon, SlidersIcon, SunIcon } from "./Icons";
import { Popover } from "./Popover";

const PERIODS: Period[] = ["1D", "1W", "1M", "3M", "6M", "YTD", "1Y", "3Y"];
const ACCENTS = ["#14b8a6", "#e0a526", "#3b82f6", "#a855f7", "#f97316", "#ec4899", "#84cc16"];

export function Header() {
  const s = useSettings();
  const { data: meta } = useData<Meta>("meta");

  return (
    <header className="flex flex-wrap items-center gap-x-4 gap-y-2 px-4 py-2 border-b"
      style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
      <div className="flex items-center gap-2">
        <LogoMark />
        <span className="text-[15px] font-extrabold tracking-tight">{APP_NAME}</span>
        <span className="hidden sm:inline text-[10px] font-semibold uppercase tracking-wider" style={{ color: "var(--muted)" }}>
          Macro Dashboard
        </span>
      </div>

      {/* Global timeframe: drives every performance panel */}
      <div role="radiogroup" aria-label="Performance period" className="flex rounded-md border overflow-hidden"
        style={{ borderColor: "var(--border)" }}>
        {PERIODS.map((p) => (
          <button key={p} type="button" role="radio" aria-checked={s.period === p} onClick={() => s.setPeriod(p)}
            className="px-2 py-1 text-[11px] font-bold num"
            style={s.period === p
              ? { background: "var(--accent)", color: "var(--accent-ink)" }
              : { color: "var(--ink-2)" }}>
            {p}
          </button>
        ))}
      </div>

      <div className="flex-1" />

      {meta && <FreshnessBadge meta={meta} />}

      <Popover label="Customise view" trigger={<SlidersIcon />} width={280}>
        <div className="p-3 text-[12px]">
          <div className="flex items-center justify-between mb-2">
            <span className="group-label">Customise view</span>
            <button type="button" className="text-[11px] underline" style={{ color: "var(--accent)" }} onClick={s.showAll}>Show all</button>
          </div>
          {SECTIONS.map((sec) => {
            const items = PANELS.filter((p) => p.section === sec);
            if (!items.length) return null;
            return (
              <div key={sec} className="mb-2">
                <div className="text-[10px] font-semibold uppercase mb-1" style={{ color: "var(--muted)" }}>{sec}</div>
                {items.map((p) => (
                  <label key={p.id} className="flex items-center gap-2 py-0.5 cursor-pointer">
                    <input type="checkbox" checked={!s.hidden.includes(p.id)} onChange={() => s.togglePanel(p.id)}
                      style={{ accentColor: "var(--accent)" }} />
                    {p.title}
                  </label>
                ))}
              </div>
            );
          })}
          <div className="border-t pt-2 mt-2" style={{ borderColor: "var(--border)" }}>
            <div className="group-label mb-1.5">Accent colour</div>
            <div className="flex flex-wrap gap-1.5 items-center">
              {ACCENTS.map((c) => (
                <button key={c} type="button" aria-label={`Accent ${c}`} onClick={() => s.setAccent(c)}
                  className="w-5 h-5 rounded-full border-2"
                  style={{ background: c, borderColor: s.accent === c ? "var(--ink)" : "transparent" }} />
              ))}
              <input type="color" value={s.accent} onChange={(e) => s.setAccent(e.target.value)}
                aria-label="Custom accent colour" className="w-6 h-6 bg-transparent cursor-pointer" />
            </div>
            <div className="group-label mt-3 mb-1.5">Gain / loss colours</div>
            <select value={s.palette} onChange={(e) => s.setPalette(e.target.value as "classic" | "cvd")}
              className="w-full rounded border px-1.5 py-1 text-[12px]"
              style={{ background: "var(--surface)", borderColor: "var(--border)", color: "var(--ink)" }}>
              <option value="classic">Green / Red (classic)</option>
              <option value="cvd">Blue / Red (colour-blind safe)</option>
            </select>
          </div>
        </div>
      </Popover>

      <button type="button" className="icon-btn" aria-label="Toggle light/dark theme" title="Toggle theme"
        onClick={() => s.setTheme(s.theme === "dark" ? "light" : "dark")}>
        {s.theme === "dark" ? <SunIcon /> : <MoonIcon />}
      </button>
    </header>
  );
}

/** Global freshness: the oldest section's last good update, with a warning when a section failed. */
function FreshnessBadge({ meta }: { meta: Meta }) {
  const entries = Object.entries(meta.sections);
  const failed = entries.filter(([, v]) => v.ok === false);
  const times = entries.map(([, v]) => v.updated_at).filter((t): t is string => !!t).sort();
  const oldest = times[0] ?? meta.generated_at;
  const detail = failed.length
    ? `Last update failed for: ${failed.map(([k]) => k).join(", ")}. Those panels show their previous data.`
    : `Oldest section refreshed ${new Date(oldest).toLocaleString()}`;
  return (
    <span className="text-[10.5px] inline-flex items-center gap-1.5" style={{ color: "var(--muted)" }} title={detail}>
      {failed.length > 0 && (
        <span className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
          style={{ border: "1px solid var(--neg)", color: "var(--neg)" }}>{failed.length} stale</span>
      )}
      Data refreshed {relTime(oldest)}
    </span>
  );
}
