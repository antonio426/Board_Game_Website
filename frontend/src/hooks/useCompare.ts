"use client";

import { useCallback, useSyncExternalStore } from "react";

/**
 * The games the visitor has lined up to compare, kept in localStorage.
 *
 * Comparison is a decision aid, and the decision is usually made across several
 * pages — pick one from a search, another from a recommendation, a third from a
 * tag page. Holding the selection in a page's state would lose it on the first
 * navigation, and requiring an account would put it behind a sign-in the
 * visitor has no reason to complete yet.
 */
const STORAGE_KEY = "compareGames";

// Four columns is where the table stops fitting a laptop; the API caps at the
// same number.
export const MAX_COMPARE = 4;

const EMPTY: number[] = [];

let cachedRaw: string | null = null;
let cachedIds: number[] = EMPTY;

const listeners = new Set<() => void>();

function read(): number[] {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return EMPTY;
  }
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    try {
      const parsed = raw ? JSON.parse(raw) : [];
      cachedIds = Array.isArray(parsed) ? parsed.filter((id) => typeof id === "number") : EMPTY;
    } catch {
      cachedIds = EMPTY;
    }
  }
  return cachedIds;
}

function write(ids: number[]) {
  try {
    window.localStorage.setItem(STORAGE_KEY, JSON.stringify(ids));
  } catch {
    return;
  }
  listeners.forEach((onChange) => onChange());
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useCompare() {
  const ids = useSyncExternalStore(subscribe, read, () => EMPTY);

  const toggle = useCallback((bggId: number) => {
    const current = read();
    if (current.includes(bggId)) {
      write(current.filter((id) => id !== bggId));
      return;
    }
    // Silently dropping the click past the cap would look broken; the caller
    // reads `isFull` and says so instead.
    if (current.length >= MAX_COMPARE) return;
    write([...current, bggId]);
  }, []);

  const clear = useCallback(() => write([]), []);

  return { ids, toggle, clear, isFull: ids.length >= MAX_COMPARE };
}
