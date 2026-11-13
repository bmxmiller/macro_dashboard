import { lazy, Suspense, type ComponentProps } from "react";

const EChart = lazy(() => import("./EChart"));

/** Code-split ECharts: the library loads in its own chunk on first chart render. */
export function LazyEChart(props: ComponentProps<typeof EChart>) {
  return (
    <Suspense fallback={<div className={props.className} style={props.style} aria-busy="true" />}>
      <EChart {...props} />
    </Suspense>
  );
}
