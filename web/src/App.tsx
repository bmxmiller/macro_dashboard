import { useEffect } from "react";
import { Header } from "./components/Header";
import { PANELS } from "./panels/registry";
import { useSettings } from "./state/store";

const SPAN: Record<number, string> = {
  3: "xl:col-span-3", 4: "xl:col-span-4", 6: "xl:col-span-6", 8: "xl:col-span-8", 12: "xl:col-span-12",
};

/** Pick readable ink (dark or light) for text on the accent colour. */
function inkFor(hex: string): string {
  const n = parseInt(hex.replace("#", ""), 16);
  const [r, g, b] = [(n >> 16) & 255, (n >> 8) & 255, n & 255].map((c) => {
    const s = c / 255;
    return s <= 0.03928 ? s / 12.92 : ((s + 0.055) / 1.055) ** 2.4;
  });
  return 0.2126 * r + 0.7152 * g + 0.0722 * b > 0.3 ? "#0b0b0b" : "#ffffff";
}

export default function App() {
  const { theme, palette, accent, hidden } = useSettings();

  useEffect(() => {
    const root = document.documentElement;
    root.dataset.theme = theme;
    root.dataset.palette = palette;
    root.style.setProperty("--accent", accent);
    root.style.setProperty("--accent-ink", inkFor(accent));
  }, [theme, palette, accent]);

  const visible = PANELS.filter((p) => !hidden.includes(p.id));

  return (
    <div className="min-h-full flex flex-col">
      <Header />
      {/* Full-width strips (span 12) size to their content */}
      {visible.filter((p) => p.span === 12).map(({ id, Component }) => (
        <div key={id} className="px-2 pt-2"><Component /></div>
      ))}
      <main className="grid grid-cols-1 md:grid-cols-2 xl:grid-cols-12 gap-2 p-2 auto-rows-[460px]">
        {visible.filter((p) => p.span !== 12).map(({ id, span, tall, Component }) => (
          <div key={id} className={`min-h-0 flex flex-col ${SPAN[span]} ${tall ? "row-span-2" : ""}`}>
            <Component />
          </div>
        ))}
      </main>
      <footer className="px-4 py-3 text-[10.5px] border-t" style={{ color: "var(--muted)", borderColor: "var(--border)" }}>
        Data: FRED, Yahoo Finance, Federal Reserve. Total returns include dividends. Not investment advice.
      </footer>
    </div>
  );
}
