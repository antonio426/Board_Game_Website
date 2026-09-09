"use client";

import { useEffect, useSyncExternalStore } from "react";

/**
 * The last few games this browser opened, kept in localStorage.
 *
 * Deliberately not a server-side history: it has to work before anyone signs
 * in, which is exactly when a visitor most needs to find their way back to the
 * game they were looking at two clicks ago.
 */
const STORAGE_KEY = "recentlyViewedGames";
const MAX_ENTRIES = 8;

export interface RecentGame {
  bgg_id: number;
  name: string;
  local_thumbnail?: string;
  local_image?: string;
}

const EMPTY: RecentGame[] = [];

// useSyncExternalStore compares snapshots by identity, so parsing on every read
// would re-render forever. The last parse is kept against the raw string it
// came from.
let cachedRaw: string | null = null;
let cachedGames: RecentGame[] = EMPTY;

const listeners = new Set<() => void>();

function parse(raw: string | null): RecentGame[] {
  if (!raw) return EMPTY;
  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed.filter((entry) => entry && entry.bgg_id) : EMPTY;
  } catch {
    return EMPTY;
  }
}

function read(): RecentGame[] {
  let raw: string | null = null;
  try {
    raw = window.localStorage.getItem(STORAGE_KEY);
  } catch {
    return EMPTY;
  }
  if (raw !== cachedRaw) {
    cachedRaw = raw;
    cachedGames = parse(raw);
  }
  return cachedGames;
}

function subscribe(onChange: () => void) {
  listeners.add(onChange);
  // Another tab writing the same key.
  window.addEventListener("storage", onChange);
  return () => {
    listeners.delete(onChange);
    window.removeEventListener("storage", onChange);
  };
}

export function useRecentlyViewed(): RecentGame[] {
  // The server has no localStorage, so it renders the empty list and the client
  // fills it in — the alternative is markup that differs on hydration.
  return useSyncExternalStore(subscribe, read, () => EMPTY);
}

export function useRecordRecentlyViewed(game: RecentGame | null) {
  // Serialized so the effect depends on the game's contents rather than on the
  // identity of an object the caller rebuilds every render.
  const entry = game?.bgg_id && game.name ? JSON.stringify(game) : "";

  useEffect(() => {
    if (!entry) return;
    const recorded = JSON.parse(entry) as RecentGame;
    try {
      const next = [recorded, ...read().filter((game) => game.bgg_id !== recorded.bgg_id)].slice(0, MAX_ENTRIES);
      window.localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
    } catch {
      // A browser with storage disabled simply has no history.
      return;
    }
    listeners.forEach((onChange) => onChange());
  }, [entry]);
}
