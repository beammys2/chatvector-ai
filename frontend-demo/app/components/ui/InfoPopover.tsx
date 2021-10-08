"use client";

import { Info } from "lucide-react";
import { createPortal } from "react-dom";
import { useEffect, useId, useRef, useState, type ReactNode } from "react";

const POPOVER_WIDTH = 224; // matches w-56
const VIEWPORT_PADDING = 8;

type Props = {
  label: string;
  children: ReactNode;
  contentId?: string;
};

function clampPopoverLeft(triggerCenterX: number) {
  const idealLeft = triggerCenterX - POPOVER_WIDTH / 2;
  const maxLeft = window.innerWidth - POPOVER_WIDTH - VIEWPORT_PADDING;
  return Math.max(VIEWPORT_PADDING, Math.min(idealLeft, maxLeft));
}

/**
 * Compact info icon that reveals helper text in a click-to-toggle popover.
 */
export function InfoPopover({ label, children, contentId }: Props) {
  const autoId = useId();
  const id = contentId ?? autoId;
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<{ top: number; left: number } | null>(
    null
  );
  const buttonRef = useRef<HTMLButtonElement>(null);

  useEffect(() => {
    if (!open || !buttonRef.current) {
      setPosition(null);
      return;
    }

    const updatePosition = () => {
      const rect = buttonRef.current!.getBoundingClientRect();
      setPosition({
        top: rect.bottom + 6,
        left: clampPopoverLeft(rect.left + rect.width / 2),
      });
    };

    updatePosition();

    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") setOpen(false);
    };

    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    document.addEventListener("keydown", onKeyDown);

    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      document.removeEventListener("keydown", onKeyDown);
    };
  }, [open]);

  useEffect(() => {
    if (!open) return;

    const onPointerDown = (event: PointerEvent) => {
      const target = event.target;
      if (!(target instanceof Node)) return;
      if (buttonRef.current?.contains(target)) return;

      const popover = document.getElementById(id);
      if (popover?.contains(target)) return;

      setOpen(false);
    };

    document.addEventListener("pointerdown", onPointerDown);
    return () => document.removeEventListener("pointerdown", onPointerDown);
  }, [open, id]);

  const popover =
    open && position
      ? createPortal(
          <div
            id={id}
            role="tooltip"
            className="fixed z-50 w-56 rounded-lg border border-border bg-surface px-3 py-2 text-xs leading-relaxed text-muted shadow-lg"
            style={{ top: position.top, left: position.left }}
          >
            {children}
          </div>,
          document.body
        )
      : null;

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        aria-expanded={open}
        aria-controls={id}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex rounded p-0.5 text-muted transition-colors hover:text-foreground focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-1 focus-visible:outline-accent"
      >
        <Info size={14} aria-hidden="true" />
      </button>
      {popover}
    </>
  );
}
