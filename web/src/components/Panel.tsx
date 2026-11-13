import { useRef, useState, type ReactNode } from "react";
import { toPng } from "html-to-image";
import { useSettings } from "../state/store";
import type { About } from "../types";
import { AboutButton } from "./AboutCard";
import { CloseIcon, DownloadIcon } from "./Icons";

export interface PanelProps {
  id: string;
  title: string;
  subtitle?: ReactNode;
  about?: About;
  sourceUrl?: string;
  stale?: string | null;          // error message when the pipeline section failed
  headerRight?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** The shared shell: header bar, About, PNG export, hide, stale badge. */
export function Panel({ id, title, subtitle, about, sourceUrl, stale, headerRight, className = "", children }: PanelProps) {
  const ref = useRef<HTMLElement>(null);
  const toggle = useSettings((s) => s.togglePanel);
  const [busy, setBusy] = useState(false);

  async function exportPng() {
    if (!ref.current) return;
    setBusy(true);
    try {
      const bg = getComputedStyle(document.body).backgroundColor;
      const url = await toPng(ref.current, {
        pixelRatio: 2, backgroundColor: bg,
        filter: (n) => !(n instanceof HTMLElement && n.dataset.noExport !== undefined),
      });
      const a = document.createElement("a");
      a.href = url;
      a.download = `${id}-${new Date().toISOString().slice(0, 10)}.png`;
      a.click();
    } catch (e) {
      console.error("export failed", e);
    } finally {
      setBusy(false);
    }
  }

  return (
    <section ref={ref} aria-labelledby={`${id}-title`}
      className={`flex flex-col min-h-0 rounded-md border overflow-hidden ${className}`}
      style={{ background: "var(--surface)", borderColor: "var(--border)" }}>
      <header className="flex items-center gap-2 px-3 py-1.5 shrink-0"
        style={{ background: "var(--accent)", color: "var(--accent-ink)" }}>
        <div className="min-w-0 flex-1">
          <h2 id={`${id}-title`} className="m-0 text-[11px] font-extrabold uppercase tracking-wider truncate">{title}</h2>
          {subtitle && <div className="text-[9.5px] font-semibold uppercase tracking-wide opacity-75 truncate">{subtitle}</div>}
        </div>
        {stale && (
          <span title={`Last update failed: ${stale}. Showing previous data.`}
            className="text-[9px] font-bold uppercase px-1.5 py-0.5 rounded"
            style={{ background: "var(--accent-ink)", color: "var(--accent)" }}>Stale</span>
        )}
        {headerRight}
        <div className="flex items-center gap-0.5 header-actions" data-no-export>
          {about && <AboutButton title={title} about={about} sourceUrl={sourceUrl} />}
          <button type="button" className="icon-btn" aria-label={`Export ${title} as PNG`} title="Export PNG"
            onClick={exportPng} disabled={busy}><DownloadIcon /></button>
          <button type="button" className="icon-btn" aria-label={`Hide ${title}`} title="Hide panel"
            onClick={() => toggle(id)}><CloseIcon /></button>
        </div>
      </header>
      <div className="flex-1 min-h-0 overflow-auto scroll-thin">{children}</div>
    </section>
  );
}

export function PanelMessage({ children }: { children: ReactNode }) {
  return <div className="p-4 text-[12px]" style={{ color: "var(--muted)" }}>{children}</div>;
}
