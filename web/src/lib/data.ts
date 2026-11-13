import { useEffect, useState } from "react";

type State<T> = { data: T | null; error: string | null; loading: boolean };

const cache = new Map<string, Promise<unknown>>();

function load<T>(name: string): Promise<T> {
  if (!cache.has(name)) {
    const url = `${import.meta.env.BASE_URL}data/${name}.json`;
    cache.set(name, fetch(url, { cache: "no-cache" }).then((r) => {
      // Static hosts (and Vite's SPA fallback) may answer a missing file with index.html.
      const isJson = (r.headers.get("content-type") ?? "").includes("json");
      if (r.status === 404 || (r.ok && !isJson)) {
        throw new Error(`no data yet: the "${name}" section hasn't been built (run the pipeline)`);
      }
      if (!r.ok) throw new Error(`${name}.json: HTTP ${r.status}`);
      return r.json();
    }));
  }
  return cache.get(name) as Promise<T>;
}

/** Load a pipeline JSON file from /data. Results are shared between panels. */
export function useData<T>(name: string): State<T> {
  const [state, setState] = useState<State<T>>({ data: null, error: null, loading: true });
  useEffect(() => {
    let alive = true;
    load<T>(name)
      .then((data) => alive && setState({ data, error: null, loading: false }))
      .catch((e: Error) => {
        cache.delete(name);
        if (alive) setState({ data: null, error: e.message, loading: false });
      });
    return () => { alive = false; };
  }, [name]);
  return state;
}
