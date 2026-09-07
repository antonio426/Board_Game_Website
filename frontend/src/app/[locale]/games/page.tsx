"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useLocale, useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { apiFetch } from "@/lib/api";
import GameImage, { gameImageUrl } from "@/components/GameImage";
import GameFilterPanel, { type Facets, type TagVocabulary } from "@/components/GameFilterPanel";
import {
  DEFAULT_FILTERS,
  SORT_OPTIONS,
  countActive,
  fromSearchParams,
  toApiParams,
  toFacetParams,
  toSearchParams,
  type GameFilterState,
} from "@/lib/gameFilters";

interface Game {
  bgg_id: number;
  name_en: string;
  name_zh: string;
  display_name?: string;
  thumbnail: string;
  local_thumbnail?: string;
  local_image?: string;
  image?: string;
  min_players: number;
  max_players: number;
  min_playtime: number;
  max_playtime: number;
  bgg_rating: number;
  bgg_rank: number;
  bgg_weight: number;
  users_rated?: number;
  quality_score?: number;
  is_expansion?: boolean;
  year_published: number;
}

interface GamesResponse {
  games: Game[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

const SORT_LABEL_KEYS: Record<string, string> = {
  quality: "sortQuality",
  rating: "sortRating",
  rank: "sortRank",
  name: "sortName",
  weight: "sortWeight",
  year: "sortYear",
};

function GamesPageInner() {
  const t = useTranslations("games");
  const tc = useTranslations("common");
  const locale = useLocale();
  const router = useRouter();
  const searchParams = useSearchParams();

  const [filters, setFilters] = useState<GameFilterState>(() => fromSearchParams(new URLSearchParams(searchParams.toString())));
  const [draftQuery, setDraftQuery] = useState(filters.q);
  const [data, setData] = useState<GamesResponse | null>(null);
  const [facets, setFacets] = useState<Facets | null>(null);
  const [categories, setCategories] = useState<TagVocabulary[]>([]);
  const [mechanics, setMechanics] = useState<TagVocabulary[]>([]);
  const [loading, setLoading] = useState(true);
  const [showFilters, setShowFilters] = useState(true);
  const [showTop, setShowTop] = useState(false);

  useEffect(() => {
    const onScroll = () => setShowTop(window.scrollY > 400);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  useEffect(() => {
    apiFetch<TagVocabulary[]>("/games/categories").then(setCategories).catch(() => {});
    apiFetch<TagVocabulary[]>("/games/mechanics").then(setMechanics).catch(() => {});
  }, []);

  /** One place changes filters: it updates state and the shareable URL together. */
  const applyFilters = useCallback((next: GameFilterState) => {
    setFilters(next);
    const query = toSearchParams(next).toString();
    router.replace(query ? `?${query}` : "?", { scroll: false });
  }, [router]);

  /* eslint-disable react-hooks/set-state-in-effect */
  useEffect(() => {
    let cancelled = false;
    setLoading(true);

    apiFetch<GamesResponse>(`/games/search?${toApiParams(filters, locale).toString()}`)
      .then((response) => {
        if (!cancelled) setData(response);
      })
      .catch(() => {})
      .finally(() => {
        if (!cancelled) setLoading(false);
      });

    return () => { cancelled = true; };
  }, [filters, locale]);

  useEffect(() => {
    let cancelled = false;
    apiFetch<Facets>(`/games/facets?${toFacetParams(filters, locale).toString()}`)
      .then((response) => {
        if (!cancelled) setFacets(response);
      })
      .catch(() => {});
    return () => { cancelled = true; };
  }, [filters, locale]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const goRandom = async () => {
    try {
      const game = await apiFetch<{ bgg_id: number }>(`/games/random?locale=${locale}`);
      if (game?.bgg_id) router.push(`/${locale}/games/${game.bgg_id}`);
    } catch {}
  };

  const games = data?.games || [];
  const activeCount = countActive(filters);

  return (
    <main className="mx-auto max-w-7xl px-5 py-8">
      <div className="mb-6 flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl tracking-wide">{t("title")}</h1>
          {data && (
            <p className="mt-1 text-sm" style={{ color: "var(--color-text-muted)" }}>
              {data.total.toLocaleString()} {t("results")}
            </p>
          )}
        </div>
        <div className="flex gap-2">
          <button
            onClick={goRandom}
            className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors hover:brightness-125"
            style={{ background: "rgba(217,119,6,0.12)", border: "1px solid rgba(217,119,6,0.3)", color: "#FBBF24" }}
          >
            {t("random")}
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "#CBD5E1" }}
          >
            {t("filter")}{activeCount > 0 ? ` (${activeCount})` : ""}
          </button>
        </div>
      </div>

      <div className="mb-5 flex flex-wrap items-center gap-3">
        <form
          className="relative flex-1 min-w-[200px] max-w-sm"
          onSubmit={(event) => {
            event.preventDefault();
            applyFilters({ ...filters, q: draftQuery, page: 1 });
          }}
        >
          <input
            type="text"
            placeholder={t("search")}
            value={draftQuery}
            onChange={(event) => setDraftQuery(event.target.value)}
            onBlur={() => applyFilters({ ...filters, q: draftQuery, page: 1 })}
            className="w-full px-3 py-2.5 text-sm"
          />
        </form>

        <select
          value={filters.sort}
          onChange={(event) => applyFilters({ ...filters, sort: event.target.value, page: 1 })}
          className="py-2.5 text-sm"
        >
          {SORT_OPTIONS.map((option) => (
            <option key={option} value={option}>{t(SORT_LABEL_KEYS[option])}</option>
          ))}
        </select>

        {activeCount > 0 && (
          <button
            onClick={() => {
              setDraftQuery("");
              applyFilters({ ...DEFAULT_FILTERS });
            }}
            className="rounded-lg px-3 py-2 text-sm underline"
            style={{ color: "var(--color-text-muted)" }}
          >
            {t("clearFilters")}
          </button>
        )}
      </div>

      {showFilters && (
        <GameFilterPanel
          filters={filters}
          onChange={applyFilters}
          facets={facets}
          categories={categories}
          mechanics={mechanics}
        />
      )}

      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, index) => (
            <div key={index} className="overflow-hidden" style={{ borderRadius: "var(--radius-xl)", border: "1px solid var(--color-border)" }}>
              <div className="skeleton aspect-[4/3]" />
              <div style={{ background: "var(--color-surface)", padding: "12px" }}>
                <div className="skeleton" style={{ width: "70%", height: 14, marginBottom: 8 }} />
                <div className="flex gap-2">
                  <div className="skeleton" style={{ width: 48, height: 20, borderRadius: 9999 }} />
                  <div className="skeleton" style={{ width: 64, height: 20, borderRadius: 9999 }} />
                </div>
              </div>
            </div>
          ))}
        </div>
      ) : games.length === 0 ? (
        <div className="py-20 text-center">
          <p style={{ color: "var(--color-text-muted)" }}>{tc("noResults")}</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {games.map((game) => (
              <Link key={game.bgg_id} href={`/games/${game.bgg_id}`} className="game-card group">
                <div className="aspect-[4/3] overflow-hidden" style={{ background: "var(--color-muted)" }}>
                  <GameImage src={gameImageUrl(game)} alt={game.name_en} className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
                </div>
                <div className="p-3">
                  <h3 className="truncate text-sm font-semibold" style={{ color: "#F1F5F9" }}>
                    {game.display_name || game.name_zh || game.name_en}
                  </h3>
                  {game.name_zh && (
                    <p className="truncate text-xs mt-0.5" style={{ color: "var(--color-text-muted)" }}>{game.name_en}</p>
                  )}
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    <span className="badge badge-rating">{(game.bgg_rating || 0).toFixed(1)}</span>
                    <span className="badge badge-players">{game.min_players}-{game.max_players}</span>
                    <span className="badge badge-time">{game.min_playtime}-{game.max_playtime}m</span>
                    {game.bgg_weight > 0 && <span className="badge badge-rank">{game.bgg_weight.toFixed(1)}/5</span>}
                  </div>
                </div>
              </Link>
            ))}
          </div>

          {data && data.total_pages > 1 && (
            <div className="mt-8 flex items-center justify-center gap-3">
              <button
                onClick={() => applyFilters({ ...filters, page: Math.max(1, filters.page - 1) })}
                disabled={filters.page <= 1}
                className="rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-30"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "#CBD5E1" }}
              >
                {t("prev")}
              </button>
              <span className="text-sm" style={{ color: "var(--color-text-secondary)" }}>
                {t("page")} {filters.page} {t("of")} {data.total_pages}
              </span>
              <button
                onClick={() => applyFilters({ ...filters, page: Math.min(data.total_pages, filters.page + 1) })}
                disabled={filters.page >= data.total_pages}
                className="rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-30"
                style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "#CBD5E1" }}
              >
                {t("next")}
              </button>
            </div>
          )}
        </>
      )}

      {showTop && (
        <button
          onClick={() => window.scrollTo({ top: 0, behavior: "smooth" })}
          className="fixed bottom-6 right-6 z-30 rounded-full px-4 py-2.5 text-sm font-medium shadow-lg transition-all hover:brightness-125"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "#CBD5E1" }}
        >
          {t("backToTop")}
        </button>
      )}
    </main>
  );
}

export default function GamesPage() {
  return (
    <Suspense fallback={null}>
      <GamesPageInner />
    </Suspense>
  );
}
