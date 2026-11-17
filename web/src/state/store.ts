import { create } from "zustand";
import { createJSONStorage, persist } from "zustand/middleware";
import type { Period } from "../types";

export type Theme = "dark" | "light";
export type Palette = "classic" | "cvd";
export type HeatSize = "sqrt" | "cap" | "equal";   // S&P 500 heat map area: square root of market cap (balanced), market cap, or equal

interface Settings {
  period: Period;
  theme: Theme;
  palette: Palette;
  accent: string;
  hidden: string[];              // panel ids hidden via Customise View
  heatSize: HeatSize;
  setHeatSize: (h: HeatSize) => void;
  setPeriod: (p: Period) => void;
  setTheme: (t: Theme) => void;
  setPalette: (p: Palette) => void;
  setAccent: (c: string) => void;
  togglePanel: (id: string) => void;
  showAll: () => void;
}

// localStorage can throw (private mode, blocked storage): fall back to memory.
const safeStorage = createJSONStorage(() => {
  try {
    const k = "__probe__";
    localStorage.setItem(k, k);
    localStorage.removeItem(k);
    return localStorage;
  } catch {
    const mem = new Map<string, string>();
    return {
      getItem: (k: string) => mem.get(k) ?? null,
      setItem: (k: string, v: string) => void mem.set(k, v),
      removeItem: (k: string) => void mem.delete(k),
    };
  }
});

export const useSettings = create<Settings>()(
  persist(
    (set) => ({
      period: "6M",
      theme: "dark",
      palette: "classic",
      accent: "#14b8a6",
      hidden: [],
      heatSize: "sqrt",
      setHeatSize: (heatSize) => set({ heatSize }),
      setPeriod: (period) => set({ period }),
      setTheme: (theme) => set({ theme }),
      setPalette: (palette) => set({ palette }),
      setAccent: (accent) => set({ accent }),
      togglePanel: (id) =>
        set((s) => ({ hidden: s.hidden.includes(id) ? s.hidden.filter((x) => x !== id) : [...s.hidden, id] })),
      showAll: () => set({ hidden: [] }),
    }),
    { name: "macrolens-settings", storage: safeStorage, version: 1 },
  ),
);
