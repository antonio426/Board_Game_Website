"use client";

import { useState } from "react";
import type { TagState } from "@/lib/gameFilters";

export interface ChipOption {
  name: string;
  label: string;
  count?: number;
}

interface Props {
  title: string;
  options: ChipOption[];
  stateOf: (name: string) => TagState;
  onToggle: (name: string) => void;
  moreLabel: string;
  lessLabel: string;
  hint?: string;
  collapsedCount?: number;
}

const STYLES: Record<TagState, React.CSSProperties> = {
  off: {
    background: "var(--color-surface)",
    border: "1px solid var(--color-border)",
    color: "#CBD5E1",
  },
  include: {
    background: "rgba(34,197,94,0.16)",
    border: "1px solid rgba(34,197,94,0.5)",
    color: "#86EFAC",
  },
  exclude: {
    background: "rgba(239,68,68,0.14)",
    border: "1px solid rgba(239,68,68,0.45)",
    color: "#FCA5A5",
    textDecoration: "line-through",
  },
};

/**
 * One tag vocabulary as clickable chips. A chip cycles off -> include ->
 * exclude, which is the only way to express "anything but wargames" without a
 * second control, and the count shows how many games would remain.
 */
export default function FilterChips({
  title, options, stateOf, onToggle, moreLabel, lessLabel, hint, collapsedCount = 18,
}: Props) {
  const [expanded, setExpanded] = useState(false);
  const visible = expanded ? options : options.slice(0, collapsedCount);

  return (
    <div>
      <div className="mb-2 flex items-baseline gap-2">
        <span className="text-xs font-medium" style={{ color: "var(--color-text-secondary)" }}>{title}</span>
        {hint && <span className="text-[11px]" style={{ color: "var(--color-text-muted)" }}>{hint}</span>}
      </div>

      <div className="flex flex-wrap gap-1.5">
        {visible.map((option) => {
          const state = stateOf(option.name);
          const empty = option.count === 0 && state === "off";
          return (
            <button
              key={option.name}
              type="button"
              onClick={() => onToggle(option.name)}
              aria-pressed={state !== "off"}
              className="rounded-full px-2.5 py-1 text-xs transition-colors hover:brightness-125"
              style={{ ...STYLES[state], opacity: empty ? 0.35 : 1 }}
            >
              {option.label}
              {option.count !== undefined && (
                <span style={{ opacity: 0.65 }}> {option.count}</span>
              )}
            </button>
          );
        })}

        {options.length > collapsedCount && (
          <button
            type="button"
            onClick={() => setExpanded(!expanded)}
            className="rounded-full px-2.5 py-1 text-xs underline"
            style={{ color: "var(--color-text-muted)" }}
          >
            {expanded ? lessLabel : `${moreLabel} (${options.length - collapsedCount})`}
          </button>
        )}
      </div>
    </div>
  );
}
