import type { Meta } from "../types";
import { useData } from "./data";

/** Error message when the pipeline section's last update failed, else null. */
export function useStale(section: string): string | null {
  const { data: meta } = useData<Meta>("meta");
  const s = meta?.sections[section];
  return s?.ok === false ? s.error ?? "update failed" : null;
}
