/**
 * Filter state for the games page, and its two serializations: the browser URL
 * (so a filtered view can be shared or reloaded) and the API query string.
 */

export type TagState = "off" | "include" | "exclude";

export interface GameFilterState {
  q: string;
  /** Match on meaning rather than on the name. */
  semantic: boolean;
  sort: string;
  page: number;
  family: string;
  players: string;
  bestAtPlayers: boolean;
  playtimeMax: string;
  weightBand: string;
  languageBand: string;
  ageMax: string;
  yearRange: string;
  minRatings: string;
  categories: string[];
  mechanics: string[];
  excludeCategories: string[];
  excludeMechanics: string[];
  includeExpansions: boolean;
}

export const DEFAULT_FILTERS: GameFilterState = {
  q: "",
  semantic: false,
  sort: "quality",
  page: 1,
  family: "",
  players: "",
  bestAtPlayers: false,
  playtimeMax: "",
  weightBand: "",
  languageBand: "",
  ageMax: "",
  yearRange: "",
  minRatings: "",
  categories: [],
  mechanics: [],
  excludeCategories: [],
  excludeMechanics: [],
  includeExpansions: false,
};

export const SORT_OPTIONS = ["quality", "popular", "rating", "rank", "name", "weight", "year"] as const;
export const PLAYER_OPTIONS = [1, 2, 3, 4, 5, 6, 8] as const;
export const PLAYTIME_OPTIONS = [30, 60, 120, 240] as const;

/** BGG's own top-level families — how a player describes an evening. */
export const FAMILY_OPTIONS = [
  "strategygames", "familygames", "partygames", "thematic",
  "abstracts", "wargames", "childrensgames", "cgs",
] as const;

/** How much text the game makes you read, in three answers instead of five. */
export const LANGUAGE_OPTIONS = ["low", "medium", "high"] as const;
export const AGE_OPTIONS = [6, 8, 10, 12] as const;
export const YEAR_OPTIONS = ["recent", "modern", "classic"] as const;
export const YEAR_RANGES: Record<string, { from?: number; to?: number }> = {
  recent: { from: 2021 },
  modern: { from: 2016 },
  classic: { to: 2005 },
};
export const POPULARITY_OPTIONS = [100, 1000] as const;

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
    semantic: params.get("mode") === "concept",
    sort: params.get("sort") || DEFAULT_FILTERS.sort,
    page: Math.max(1, Number(params.get("page")) || 1),
    family: params.get("fam") || "",
    players: params.get("players") || "",
    bestAtPlayers: params.get("best") === "1",
    playtimeMax: params.get("time") || "",
    weightBand: params.get("weight") || "",
    languageBand: params.get("lang") || "",
    ageMax: params.get("age") || "",
    yearRange: params.get("year") || "",
    minRatings: params.get("pop") || "",
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
  if (filters.semantic) params.set("mode", "concept");
  if (filters.sort !== DEFAULT_FILTERS.sort) params.set("sort", filters.sort);
  if (filters.page > 1) params.set("page", String(filters.page));
  if (filters.family) params.set("fam", filters.family);
  if (filters.players) params.set("players", filters.players);
  if (filters.bestAtPlayers) params.set("best", "1");
  if (filters.playtimeMax) params.set("time", filters.playtimeMax);
  if (filters.weightBand) params.set("weight", filters.weightBand);
  if (filters.languageBand) params.set("lang", filters.languageBand);
  if (filters.ageMax) params.set("age", filters.ageMax);
  if (filters.yearRange) params.set("year", filters.yearRange);
  if (filters.minRatings) params.set("pop", filters.minRatings);
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
  if (filters.q && filters.semantic) params.set("semantic", "true");
  if (filters.players) {
    params.set("players", filters.players);
    if (filters.bestAtPlayers) params.set("best_at_players", "true");
  }
  if (filters.playtimeMax) params.set("playtime_max", filters.playtimeMax);

  const band = WEIGHT_BANDS[filters.weightBand];
  if (band?.min !== undefined) params.set("min_weight", String(band.min));
  if (band?.max !== undefined) params.set("max_weight", String(band.max));

  if (filters.family) params.set("family", filters.family);
  if (filters.languageBand) params.set("language_dependence", filters.languageBand);
  if (filters.ageMax) params.set("max_min_age", filters.ageMax);
  if (filters.minRatings) params.set("min_ratings", filters.minRatings);

  const years = YEAR_RANGES[filters.yearRange];
  if (years?.from !== undefined) params.set("year_from", String(years.from));
  if (years?.to !== undefined) params.set("year_to", String(years.to));

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
  if (filters.family) total += 1;
  if (filters.players) total += 1;
  if (filters.playtimeMax) total += 1;
  if (filters.weightBand) total += 1;
  if (filters.languageBand) total += 1;
  if (filters.ageMax) total += 1;
  if (filters.yearRange) total += 1;
  if (filters.minRatings) total += 1;
  // `includeExpansions` widens the result set rather than narrowing it, so it
  // does not belong in a count of applied filters.
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

/** One-tap starting points. Each is a whole filter state, not an addition. */
export const PRESETS: { key: string; filters: Partial<GameFilterState> }[] = [
  { key: "twoPlayer", filters: { players: "2", playtimeMax: "60", minRatings: "100" } },
  { key: "party", filters: { family: "partygames", players: "6", playtimeMax: "30" } },
  { key: "family", filters: { family: "familygames", languageBand: "low", playtimeMax: "60" } },
];

export function applyPreset(preset: Partial<GameFilterState>): GameFilterState {
  return { ...DEFAULT_FILTERS, ...preset };
}

export function isPresetActive(filters: GameFilterState, preset: Partial<GameFilterState>): boolean {
  const target = applyPreset(preset);
  return (Object.keys(DEFAULT_FILTERS) as (keyof GameFilterState)[])
    .filter((key) => key !== "page")
    .every((key) => String(filters[key]) === String(target[key]));
}
