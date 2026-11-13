import { useEffect, useLayoutEffect, useRef, useState, type ReactNode } from "react";
import { createPortal } from "react-dom";

/** Click-to-open popover rendered in a portal so panel overflow never clips it. */
export function Popover({
  trigger, children, label, width = 320,
}: { trigger: ReactNode; children: ReactNode; label: string; width?: number }) {
  const [open, setOpen] = useState(false);
  const [pos, setPos] = useState({ top: 0, left: 0 });
  const btn = useRef<HTMLButtonElement>(null);
  const card = useRef<HTMLDivElement>(null);

  useLayoutEffect(() => {
    if (!open || !btn.current) return;
    const r = btn.current.getBoundingClientRect();
    const left = Math.max(8, Math.min(r.left - width / 2 + r.width / 2, window.innerWidth - width - 8));
    let top = r.bottom + 6;
    const h = card.current?.offsetHeight ?? 0;
    if (top + h > window.innerHeight - 8) top = Math.max(8, r.top - h - 6);
    setPos({ top, left });
  }, [open, width]);

  useEffect(() => {
    if (!open) return;
    const onDown = (e: MouseEvent) => {
      const t = e.target as Node;
      if (!card.current?.contains(t) && !btn.current?.contains(t)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => e.key === "Escape" && setOpen(false);
    const onScroll = () => setOpen(false);
    document.addEventListener("mousedown", onDown);
    document.addEventListener("keydown", onKey);
    window.addEventListener("resize", onScroll);
    return () => {
      document.removeEventListener("mousedown", onDown);
      document.removeEventListener("keydown", onKey);
      window.removeEventListener("resize", onScroll);
    };
  }, [open]);

  return (
    <>
      <button ref={btn} type="button" className="icon-btn" aria-label={label} title={label}
        aria-expanded={open} onClick={(e) => { e.stopPropagation(); setOpen((o) => !o); }}>
        {trigger}
      </button>
      {open && createPortal(
        <div ref={card} role="dialog" aria-label={label}
          className="fixed z-50 rounded-md border shadow-2xl scroll-thin overflow-auto"
          style={{ top: pos.top, left: pos.left, width, maxHeight: "70vh",
            background: "var(--surface-2)", borderColor: "var(--border)" }}>
          {children}
        </div>,
        document.body,
      )}
    </>
  );
}
