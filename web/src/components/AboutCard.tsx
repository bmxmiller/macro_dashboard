import type { About } from "../types";
import { ExternalIcon, InfoIcon } from "./Icons";
import { Popover } from "./Popover";

export function AboutCard({ title, about, sourceUrl, extra }: {
  title: string; about: About; sourceUrl?: string; extra?: React.ReactNode;
}) {
  return (
    <div className="p-3 space-y-2.5 text-[12px] leading-relaxed" style={{ color: "var(--ink-2)" }}>
      <div className="font-semibold text-[13px]" style={{ color: "var(--ink)" }}>{title}</div>
      <Section label="What it is">{about.what}</Section>
      <Section label="Why it matters">{about.why}</Section>
      <Section label="How to read it">{about.how_to_read}</Section>
      {extra}
      {sourceUrl && (
        <a href={sourceUrl} target="_blank" rel="noopener noreferrer"
          className="inline-flex items-center gap-1 font-medium hover:underline" style={{ color: "var(--accent)" }}>
          Official source <ExternalIcon />
        </a>
      )}
    </div>
  );
}

function Section({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div>
      <div className="group-label mb-0.5">{label}</div>
      <p className="m-0">{children}</p>
    </div>
  );
}

/** ⓘ button that opens the About card. */
export function AboutButton(props: { title: string; about: About; sourceUrl?: string; extra?: React.ReactNode }) {
  return (
    <Popover label={`About ${props.title}`} trigger={<InfoIcon />}>
      <AboutCard {...props} />
    </Popover>
  );
}
