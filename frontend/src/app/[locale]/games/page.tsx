"use client";

import { useEffect, useState, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/routing";
import { apiFetch } from "@/lib/api";
import GameImage, { gameImageUrl } from "@/components/GameImage";

interface Game {
  bgg_id: number;
  name_en: string;
  name_zh: string;
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
  year_published: number;
  categories: { id: number; name: string; name_zh?: string }[];
  mechanics: { id: number; name: string; name_zh?: string }[];
}

interface GamesResponse {
  games: Game[];
  total: number;
  page: number;
  per_page: number;
  total_pages: number;
}

interface FilterState {
  page: number;
  sort: string;
  min_players: string;
  max_playtime: string;
  min_weight: string;
  max_weight: string;
  category: string;
  mechanic: string;
  q: string;
}

export default function GamesPage() {
  const t = useTranslations("games");
  const tc = useTranslations("common");
  const locale = useLocale();
  const [data, setData] = useState<GamesResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [filter, setFilter] = useState<FilterState>({
    page: 1, sort: "rank", min_players: "", max_playtime: "",
    min_weight: "", max_weight: "", category: "", mechanic: "", q: "",
  });
  const [categories, setCategories] = useState<{ name: string; name_zh: string; count: number }[]>([]);
  const [mechanics, setMechanics] = useState<{ name: string; name_zh: string; count: number }[]>([]);
  const [showFilters, setShowFilters] = useState(true);
  const [showTop, setShowTop] = useState(false);
  const router = useRouter();

  useEffect(() => {
    const onScroll = () => setShowTop(window.scrollY > 400);
    window.addEventListener("scroll", onScroll);
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  const goRandom = async () => {
    try {
      const res = await apiFetch<{ bgg_id: number }>("/games/random");
      if (res?.bgg_id) router.push(`/games/${res.bgg_id}`);
    } catch {}
  };

  useEffect(() => {
    apiFetch<{ name: string; name_zh: string; count: number }[]>("/games/categories").then(setCategories).catch(() => {});
    apiFetch<{ name: string; name_zh: string; count: number }[]>("/games/mechanics").then(setMechanics).catch(() => {});
  }, []);

  /* eslint-disable react-hooks/set-state-in-effect */
  const fetchGames = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams();
    params.set("page", String(filter.page));
    params.set("sort", filter.sort);
    if (filter.q) params.set("q", filter.q);
    if (filter.min_players) params.set("min_players", filter.min_players);
    if (filter.max_playtime) params.set("max_playtime", filter.max_playtime);
    if (filter.min_weight) params.set("min_weight", filter.min_weight);
    if (filter.max_weight) params.set("max_weight", filter.max_weight);
    if (filter.category) params.set("category", filter.category);
    if (filter.mechanic) params.set("mechanic", filter.mechanic);
    try {
      const res = await apiFetch<GamesResponse>(`/games?${params.toString()}`);
      setData(res);
    } catch {
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => { fetchGames(); }, [fetchGames]);
  /* eslint-enable react-hooks/set-state-in-effect */

  const updateFilter = (key: keyof FilterState, value: string) => {
    setFilter((prev) => ({ ...prev, [key]: value, page: key !== "page" ? 1 : Number(value) || 1 }));
  };

  const games = data?.games || [];

  return (
    <main className="mx-auto max-w-7xl px-5 py-8">
      <div className="mb-6 flex items-center justify-between">
        <h1 className="font-display text-3xl tracking-wide">{t("title")}</h1>
        <div className="flex gap-2">
          <button
            onClick={goRandom}
            className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors hover:brightness-125"
            style={{ background: 'rgba(217,119,6,0.12)', border: '1px solid rgba(217,119,6,0.3)', color: '#FBBF24' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><circle cx="16" cy="16" r="1.5"/><circle cx="16" cy="8" r="1.5"/><circle cx="8" cy="16" r="1.5"/></svg>
            {t("random")}
          </button>
          <button
            onClick={() => setShowFilters(!showFilters)}
            className="flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium transition-colors"
            style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: '#CBD5E1' }}
          >
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M3 5h18M3 12h12M3 19h6"/></svg>
            {t("filter")}
          </button>
        </div>
      </div>

      <div className="mb-5 flex flex-wrap gap-3">
        <div className="relative flex-1 min-w-[200px] max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="2"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <input
            type="text"
            placeholder={t("search")}
            value={filter.q}
            onChange={(e) => updateFilter("q", e.target.value)}
            className="w-full pl-10 pr-3 py-2.5 text-sm"
          />
        </div>
        <select value={filter.sort} onChange={(e) => updateFilter("sort", e.target.value)} className="py-2.5 text-sm">
          <option value="rank">{t("sortRank")}</option>
          <option value="rating">{t("sortRating")}</option>
          <option value="name">{t("sortName")}</option>
          <option value="weight">{t("sortWeight")}</option>
          <option value="year">{t("sortYear")}</option>
        </select>
      </div>

      {showFilters && (
        <div className="mb-6 grid grid-cols-2 gap-3 rounded-xl p-5 sm:grid-cols-3 lg:grid-cols-5" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
          <div>
            <label className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>{t("playersFilter")}</label>
            <select value={filter.min_players} onChange={(e) => updateFilter("min_players", e.target.value)} className="w-full py-2 text-sm">
              <option value="">-</option>
              {[1, 2, 3, 4, 5, 6, 8].map((n) => <option key={n} value={n}>{n}+</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>{t("playtimeFilter")}</label>
            <select value={filter.max_playtime} onChange={(e) => updateFilter("max_playtime", e.target.value)} className="w-full py-2 text-sm">
              <option value="">-</option>
              {[30, 60, 90, 120, 180, 240].map((n) => <option key={n} value={n}>&le;{n}</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>{t("weightFilter")}</label>
            <div className="flex gap-1">
              <input type="number" step="0.5" min="1" max="5" placeholder={tc("min")} value={filter.min_weight} onChange={(e) => updateFilter("min_weight", e.target.value)} className="w-full py-2 text-sm" />
              <input type="number" step="0.5" min="1" max="5" placeholder={tc("max")} value={filter.max_weight} onChange={(e) => updateFilter("max_weight", e.target.value)} className="w-full py-2 text-sm" />
            </div>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>{t("categoryFilter")}</label>
            <select value={filter.category} onChange={(e) => updateFilter("category", e.target.value)} className="w-full py-2 text-sm">
              <option value="">-</option>
              {categories.map((c) => <option key={c.name} value={c.name}>{locale === "zh" && c.name_zh ? c.name_zh : c.name} ({c.count})</option>)}
            </select>
          </div>
          <div>
            <label className="mb-1.5 block text-xs font-medium" style={{ color: 'var(--color-text-secondary)' }}>{t("mechanicFilter")}</label>
            <select value={filter.mechanic} onChange={(e) => updateFilter("mechanic", e.target.value)} className="w-full py-2 text-sm">
              <option value="">-</option>
              {mechanics.map((m) => <option key={m.name} value={m.name}>{locale === "zh" && m.name_zh ? m.name_zh : m.name} ({m.count})</option>)}
            </select>
          </div>
        </div>
      )}

          {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="overflow-hidden" style={{ borderRadius: 'var(--radius-xl)', border: '1px solid var(--color-border)' }}>
              <div className="skeleton aspect-[4/3]" />
              <div style={{ background: 'var(--color-surface)', padding: '12px' }}>
                <div className="skeleton" style={{ width: '70%', height: 14, marginBottom: 8 }} />
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
          <svg className="mx-auto mb-4" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#64748B" strokeWidth="1.5"><circle cx="11" cy="11" r="8"/><path d="M21 21l-4.35-4.35"/></svg>
          <p style={{ color: 'var(--color-text-muted)' }}>{tc("noResults")}</p>
        </div>
      ) : (
        <>
          <div className="grid gap-4 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4">
            {games.map((game) => {
              const name = game.name_zh || game.name_en;
              return (
                <Link key={game.bgg_id} href={`/games/${game.bgg_id}`} className="game-card group">
                  <div className="aspect-[4/3] overflow-hidden" style={{ background: 'var(--color-muted)' }}>
                    <GameImage src={gameImageUrl(game)} alt={game.name_en} className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
                  </div>
                  <div className="p-3">
                    <h3 className="truncate text-sm font-semibold" style={{ color: '#F1F5F9' }}>
                      {name}
                    </h3>
                    {game.name_zh && (
                      <p className="truncate text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>{game.name_en}</p>
                    )}
                    <div className="mt-2 flex flex-wrap gap-1.5">
                      <span className="badge badge-rating">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="#FBBF24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                        {game.bgg_rating}
                      </span>
                      <span className="badge badge-players">{game.min_players}-{game.max_players}</span>
                      <span className="badge badge-time">{game.min_playtime}-{game.max_playtime}m</span>
                      {game.bgg_rank < 99999 && <span className="badge badge-rank">#{game.bgg_rank}</span>}
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>

          {data && data.total_pages > 1 && (
            <div className="mt-8 flex items-center justify-center gap-3">
              <button
                onClick={() => updateFilter("page", String(Math.max(1, filter.page - 1)))}
                disabled={filter.page <= 1}
                className="rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-30"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: '#CBD5E1' }}
              >
                {t("prev")}
              </button>
              <span className="text-sm" style={{ color: 'var(--color-text-secondary)' }}>
                {t("page")} {filter.page} {t("of")} {data.total_pages}
              </span>
              <button
                onClick={() => updateFilter("page", String(Math.min(data.total_pages, filter.page + 1)))}
                disabled={filter.page >= data.total_pages}
                className="rounded-lg px-4 py-2 text-sm font-medium transition-colors disabled:opacity-30"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: '#CBD5E1' }}
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
          className="fixed bottom-6 right-6 z-30 flex items-center gap-2 rounded-full px-4 py-2.5 text-sm font-medium shadow-lg transition-all hover:brightness-125"
          style={{ background: "var(--color-surface)", border: "1px solid var(--color-border)", color: "#CBD5E1" }}
          aria-label={t("backToTop")}
        >
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><polyline points="18 15 12 9 6 15"/></svg>
          {t("backToTop")}
        </button>
      )}
    </main>
  );
}
