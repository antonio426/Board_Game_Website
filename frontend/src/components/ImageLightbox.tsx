"use client";

import { useEffect } from "react";
import { createPortal } from "react-dom";

/**
 * Full-screen view of one image, rendered into document.body.
 *
 * A portal rather than a nested div: the detail page wraps its cover art in an
 * `overflow-hidden` rounded card, which clips any child that tries to grow past
 * it however high its z-index goes.
 */
export default function ImageLightbox({
  src,
  alt,
  closeLabel,
  onClose,
}: {
  src: string;
  alt: string;
  closeLabel: string;
  onClose: () => void;
}) {
  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") onClose();
    };
    document.addEventListener("keydown", onKeyDown);
    // The page behind must not scroll while the overlay is up.
    const previousOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => {
      document.removeEventListener("keydown", onKeyDown);
      document.body.style.overflow = previousOverflow;
    };
  }, [onClose]);

  // Only ever mounted by a click, so there is no server render to match.
  if (typeof document === "undefined") return null;

  return createPortal(
    <div
      role="dialog"
      aria-modal="true"
      aria-label={alt}
      onClick={onClose}
      className="fixed inset-0 z-50 flex items-center justify-center p-6"
      style={{ background: "rgba(2,6,23,0.92)" }}
    >
      <button
        type="button"
        aria-label={closeLabel}
        onClick={onClose}
        className="absolute right-5 top-5 rounded-lg px-3 py-2 text-sm"
        style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "#CBD5E1" }}
      >
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
          <line x1="18" y1="6" x2="6" y2="18" />
          <line x1="6" y1="6" x2="18" y2="18" />
        </svg>
      </button>
      <img
        src={src}
        alt={alt}
        onClick={(event) => event.stopPropagation()}
        className="max-h-full max-w-full rounded-xl object-contain"
      />
    </div>,
    document.body,
  );
}
