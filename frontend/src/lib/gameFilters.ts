/**
 * Filter state for the games page, and its two serializations: the browser URL
 * (so a filtered view can be shared or reloaded) and the API query string.
 */

export type TagState = "off" | "include" | "exclude";

export interface GameFilterState {
  q: string;
  sort: string;
  page: number;
  players: string;
  bestAtPlayers: boolean;
  playtimeMax: string;
  weightBand: string;
  categories: string[];
  mechanics: string[];
  excludeCategories: string[];
  excludeMechanics: string[];
  includeExpansions: boolean;
}

export const DEFAULT_FILTERS: GameFilterState = {
  q: "",
  sort: "quality",
  page: 1,
  players: "",
  bestAtPlayers: false,
  playtimeMax: "",
  weightBand: "",
  categories: [],
  mechanics: [],
  excludeCategories: [],
  excludeMechanics: [],
  includeExpansions: false,
};

export const SORT_OPTIONS = ["quality", "rating", "rank", "name", "weight", "year"] as const;
export const PLAYER_OPTIONS = [1, 2, 3, 4, 5, 6, 8] as const;
export const PLAYTIME_OPTIONS = [30, 60, 120, 240] as const;

/** Complexity bands, in bgg_weight units (1 = trivial, 5 = brain burner). */
export const WEIGHT_BANDS: Record<string, { min?: number; max?: number }> = {
  light: { max: 2.0 },
  medium: { min: 2.0, max: 3.5 },
  heavy: { min: 3.5 },
};

const LIST_KEYS = ["categories", "mechanics", "excludeCategories", "excludeMechanics"] as const;

export function fromSearchParams(params: URLSearchParams): GameFilterState {
  const list = (key: string) => (params.get(key) || "").split(",").filter(Boolean);
  // `category`/`mechanic` are the older link format, still out there in shared
  // URLs; they were read by nothing, so every tag-page link landed unfiltered.
  const tags = (short: string, legacy: string) => (list(short).length ? list(short) : list(legacy));
  return {
    q: params.get("q") || "",
    sort: params.get("sort") || DEFAULT_FILTERS.sort,
    page: Math.max(1, Number(params.get("page")) || 1),
    players: params.get("players") || "",
    bestAtPlayers: params.get("best") === "1",
    playtimeMax: params.get("time") || "",
    weightBand: params.get("weight") || "",
    categories: tags("cat", "category"),
    mechanics: tags("mech", "mechanic"),
    excludeCategories: list("xcat"),
    excludeMechanics: list("xmech"),
    includeExpansions: params.get("expansions") === "1",
  };
}

/** The shareable URL — only non-default values, so links stay readable. */
export function toSearchParams(filters: GameFilterState): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q) params.set("q", filters.q);
  if (filters.sort !== DEFAULT_FILTERS.sort) params.set("sort", filters.sort);
  if (filters.page > 1) params.set("page", String(filters.page));
  if (filters.players) params.set("players", filters.players);
  if (filters.bestAtPlayers) params.set("best", "1");
  if (filters.playtimeMax) params.set("time", filters.playtimeMax);
  if (filters.weightBand) params.set("weight", filters.weightBand);
  if (filters.categories.length) params.set("cat", filters.categories.join(","));
  if (filters.mechanics.length) params.set("mech", filters.mechanics.join(","));
  if (filters.excludeCategories.length) params.set("xcat", filters.excludeCategories.join(","));
  if (filters.excludeMechanics.length) params.set("xmech", filters.excludeMechanics.join(","));
  if (filters.includeExpansions) params.set("expansions", "1");
  return params;
}

export function toApiParams(filters: GameFilterState, locale: string, perPage = 24): URLSearchParams {
  const params = new URLSearchParams();
  params.set("locale", locale);
  params.set("page", String(filters.page));
  params.set("per_page", String(perPage));
  params.set("sort", filters.sort);

  if (filters.q) params.set("q", filters.q);
  if (filters.players) {
    params.set("players", filters.players);
    if (filters.bestAtPlayers) params.set("best_at_players", "true");
  }
  if (filters.playtimeMax) params.set("playtime_max", filters.playtimeMax);

  const band = WEIGHT_BANDS[filters.weightBand];
  if (band?.min !== undefined) params.set("min_weight", String(band.min));
  if (band?.max !== undefined) params.set("max_weight", String(band.max));

  if (filters.categories.length) params.set("categories", filters.categories.join(","));
  if (filters.mechanics.length) params.set("mechanics", filters.mechanics.join(","));
  if (filters.excludeCategories.length) params.set("exclude_categories", filters.excludeCategories.join(","));
  if (filters.excludeMechanics.length) params.set("exclude_mechanics", filters.excludeMechanics.join(","));
  if (filters.includeExpansions) params.set("include_expansions", "true");

  return params;
}

/** Facet counts describe the options left, so they ignore page and sort. */
export function toFacetParams(filters: GameFilterState, locale: string): URLSearchParams {
  const params = toApiParams(filters, locale);
  ["page", "per_page", "sort"].forEach((key) => params.delete(key));
  return params;
}

export function countActive(filters: GameFilterState): number {
  let total = 0;
  if (filters.q) total += 1;
  if (filters.players) total += 1;
  if (filters.playtimeMax) total += 1;
  if (filters.weightBand) total += 1;
  if (filters.includeExpansions) total += 1;
  LIST_KEYS.forEach((key) => {
    total += filters[key].length;
  });
  return total;
}

export function cycleTag(filters: GameFilterState, kind: "categories" | "mechanics", name: string): GameFilterState {
  const excludeKey = kind === "categories" ? "excludeCategories" : "excludeMechanics";
  const included = filters[kind];
  const excluded = filters[excludeKey];

  if (included.includes(name)) {
    return {
      ...filters,
      page: 1,
      [kind]: included.filter((item) => item !== name),
      [excludeKey]: [...excluded, name],
    };
  }
  if (excluded.includes(name)) {
    return { ...filters, page: 1, [excludeKey]: excluded.filter((item) => item !== name) };
  }
  return { ...filters, page: 1, [kind]: [...included, name] };
}

export function tagState(filters: GameFilterState, kind: "categories" | "mechanics", name: string): TagState {
  const excludeKey = kind === "categories" ? "excludeCategories" : "excludeMechanics";
  if (filters[kind].includes(name)) return "include";
  if (filters[excludeKey].includes(name)) return "exclude";
  return "off";
}
