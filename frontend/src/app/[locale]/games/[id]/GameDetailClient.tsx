"use client";

import { useTranslations, useLocale } from "next-intl";
import { Link } from "@/i18n/routing";
import { useState } from "react";
import { useTrackView, useTrackActions } from "@/hooks/useTracking";
import { useAuth } from "@/hooks/useAuth";
import GameImage, { gameImageUrl } from "@/components/GameImage";
import { apiFetch } from "@/lib/api";

interface Game {
  bgg_id: number;
  name_en: string;
  name_zh: string;
  description_en: string;
  description_zh: string;
  image: string;
  thumbnail: string;
  local_image?: string;
  local_thumbnail?: string;
  min_players: number;
  max_players: number;
  min_playtime: number;
  max_playtime: number;
  min_age: number;
  year_published: number;
  bgg_rating: number;
  bgg_rank: number;
  bgg_weight: number;
  users_rated: number;
  categories: { id: number; name: string; name_zh?: string }[];
  mechanics: { id: number; name: string; name_zh?: string }[];
  expansions: { bgg_id: number; name: string }[];
  series: { bgg_id: number; name: string }[];
  designers: string[];
  publishers: string[];
  recommendation_score?: number;
}

function StatBox({ label, value, accent }: { label: string; value: string; accent?: string }) {
  return (
    <div className="rounded-xl p-4" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
      <div className="text-xs font-medium mb-1" style={{ color: 'var(--color-text-muted)' }}>{label}</div>
      <div className="text-2xl font-bold" style={{ color: accent || '#F1F5F9' }}>{value}</div>
    </div>
  );
}

export default function GameDetailClient({ game, similarGames }: { game: Game; similarGames: Game[] }) {
  const t = useTranslations("common");
  const tp = useTranslations("profile");
  const locale = useLocale();
  const displayName = locale === "zh" ? (game.name_zh || game.name_en) : (game.name_en || game.name_zh);
  const altName = locale === "zh" ? (game.name_zh ? game.name_en : "") : (game.name_en ? game.name_zh : "");
  const description = locale === "zh" ? (game.description_zh || game.description_en) : (game.description_en || game.description_zh);
  const { user } = useAuth();
  const track = useTrackActions();

  useTrackView(game.bgg_id);

  const [favorited, setFavorited] = useState(false);
  const [owned, setOwned] = useState(false);
  const [userRating, setUserRating] = useState(0);
  const [hoverRating, setHoverRating] = useState(0);

  const toggleFav = async () => {
    if (!user) return;
    try {
      const data = await apiFetch<{ status: string }>("/actions/toggle", {
        method: "POST", credentials: "include",
        body: JSON.stringify({ bgg_id: game.bgg_id, action_type: "favorite" }),
      });
      setFavorited(data.status === "added");
    } catch {}
  };

  const toggleOwn = async () => {
    if (!user) return;
    try {
      const data = await apiFetch<{ status: string }>("/actions/toggle", {
        method: "POST", credentials: "include",
        body: JSON.stringify({ bgg_id: game.bgg_id, action_type: "own" }),
      });
      setOwned(data.status === "added");
    } catch {}
  };

  const submitRating = async (rating: number) => {
    if (!user) return;
    setUserRating(rating);
    track(game.bgg_id, "rate", { rating });
  };

  return (
    <main className="mx-auto max-w-5xl px-5 py-8">
      <div className="mb-8 grid gap-8 md:grid-cols-[340px_1fr]">
        <div className="overflow-hidden rounded-xl" style={{ background: 'var(--color-muted)', border: '1px solid var(--color-border)' }}>
          <GameImage src={gameImageUrl(game, false)} alt={displayName} className="w-full object-cover" />
        </div>

        <div>
          <h1 className="font-display text-3xl tracking-wide">{displayName}</h1>
          {altName && <p className="mt-1 text-lg" style={{ color: 'var(--color-text-secondary)' }}>{altName}</p>}

          {user && (
            <div className="mt-4 flex items-center gap-3">
              <button onClick={toggleFav}
                className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-all"
                style={{
                  background: favorited ? 'rgba(239,68,68,0.12)' : 'var(--color-surface)',
                  border: `1px solid ${favorited ? 'rgba(239,68,68,0.3)' : 'var(--color-border)'}`,
                  color: favorited ? '#F87171' : '#CBD5E1'
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill={favorited ? "#F87171" : "none"} stroke={favorited ? "#F87171" : "currentColor"} strokeWidth="2"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>
                {favorited ? tp("favorited") : tp("favorite")}
              </button>
              <button onClick={toggleOwn}
                className="flex items-center gap-1.5 rounded-lg px-3 py-2 text-sm font-medium transition-all"
                style={{
                  background: owned ? 'rgba(21,128,61,0.12)' : 'var(--color-surface)',
                  border: `1px solid ${owned ? 'rgba(21,128,61,0.3)' : 'var(--color-border)'}`,
                  color: owned ? '#4ADE80' : '#CBD5E1'
                }}
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/><polyline points="3.27 6.96 12 12.01 20.73 6.96"/><line x1="12" y1="22.08" x2="12" y2="12"/></svg>
                {owned ? tp("owned") : tp("own")}
              </button>
              <div className="flex items-center gap-0.5 ml-2">
                {[1,2,3,4,5,6,7,8,9,10].map((n) => (
                  <button key={n} onClick={() => submitRating(n)}
                    onMouseEnter={() => setHoverRating(n)}
                    onMouseLeave={() => setHoverRating(0)}
                    className="text-sm transition-colors px-0.5"
                    style={{ color: n <= (hoverRating || userRating) ? '#FBBF24' : '#475569' }}
                  >
                    <svg width="14" height="14" viewBox="0 0 24 24" fill={n <= (hoverRating || userRating) ? "#FBBF24" : "none"} stroke="#FBBF24" strokeWidth="1.5"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                  </button>
                ))}
                {userRating > 0 && <span className="ml-1.5 text-xs" style={{ color: 'var(--color-text-muted)' }}>{userRating}/10</span>}
              </div>
            </div>
          )}

          <div className="mt-5 grid grid-cols-2 gap-3 sm:grid-cols-3">
            <StatBox label={t("rating")} value={`★ ${game.bgg_rating}`} accent="#FBBF24" />
            <StatBox label={t("rank")} value={`#${game.bgg_rank < 99999 ? game.bgg_rank : "-"}`} accent="#4ADE80" />
            <StatBox label={t("weight")} value={`${game.bgg_weight}/5`} />
            <StatBox label={t("players")} value={`${game.min_players}–${game.max_players}`} />
            <StatBox label={t("playtime")} value={`${game.min_playtime}–${game.max_playtime}m`} />
            <StatBox label={t("year")} value={String(game.year_published || "-")} />
          </div>

          {game.designers.length > 0 && (
            <div className="mt-4">
              <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>{tp("designers")} </span>
              <span className="text-sm" style={{ color: '#CBD5E1' }}>{game.designers.join(", ")}</span>
            </div>
          )}
          {game.publishers.length > 0 && (
            <div className="mt-1">
              <span className="text-xs font-medium" style={{ color: 'var(--color-text-muted)' }}>{tp("publishers")} </span>
              <span className="text-sm" style={{ color: '#CBD5E1' }}>{game.publishers.join(", ")}</span>
            </div>
          )}

          <div className="mt-4 flex flex-wrap gap-2">
            {game.categories.map((c) => {
              const label = locale === "zh" ? (c.name_zh || c.name) : c.name;
              const key = `cat-${c.id}-${c.name}`;
              return (
                <Link key={key} href={{ pathname: "/games", query: { category: c.name } }}
                  className="rounded-full px-3 py-1 text-xs font-medium transition-colors hover:brightness-125"
                  style={{ background: 'rgba(21,128,61,0.12)', color: '#4ADE80' }}
                >{label}</Link>
              );
            })}
            {game.mechanics.map((m) => {
              const label = locale === "zh" ? (m.name_zh || m.name) : m.name;
              const key = `mech-${m.id}-${m.name}`;
              return (
                <Link key={key} href={{ pathname: "/games", query: { mechanic: m.name } }}
                  className="rounded-full px-3 py-1 text-xs font-medium transition-colors hover:brightness-125"
                  style={{ background: 'rgba(217,119,6,0.12)', color: '#FBBF24' }}
                >{label}</Link>
              );
            })}
          </div>
        </div>
      </div>

      {description && (
        <div className="mb-10">
          <h2 className="mb-3 font-display text-xl tracking-wide">{t("description")}</h2>
          <div className="rounded-xl p-5 text-sm leading-relaxed whitespace-pre-line" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: '#CBD5E1' }}>{description}</div>
        </div>
      )}

      {game.expansions.length > 0 && (
        <div className="mb-10">
          <h2 className="mb-3 font-display text-xl tracking-wide">{t("expansions")}</h2>
          <div className="flex flex-wrap gap-2">
            {game.expansions.map((e) => (
              <Link key={e.bgg_id} href={`/games/${e.bgg_id}`}
                className="rounded-lg px-4 py-2 text-sm transition-colors hover:bg-white/[0.06]"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: '#CBD5E1' }}
              >{e.name}</Link>
            ))}
          </div>
        </div>
      )}

      {similarGames.length > 0 && (
        <div className="mb-10">
          <div className="mb-4 flex items-center gap-3">
            <div className="h-6 w-1 rounded-full" style={{ background: '#15803D' }} />
            <h2 className="font-display text-xl tracking-wide">{t("similarGames")}</h2>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
            {similarGames.map((g) => (
              <Link key={g.bgg_id} href={`/games/${g.bgg_id}`}
                className="flex items-center gap-3 rounded-xl p-3 transition-colors hover:bg-white/[0.03]"
                style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
              >
                <GameImage src={gameImageUrl(g)} alt={g.name_en} className="h-14 w-14 rounded-lg object-cover" />
                <div>
                  <div className="text-sm font-semibold" style={{ color: '#F1F5F9' }}>{locale === "zh" ? (g.name_zh || g.name_en) : (g.name_en || g.name_zh)}</div>
                  <div className="text-xs mt-0.5" style={{ color: 'var(--color-text-muted)' }}>
                    ★ {g.bgg_rating} · {g.min_players}–{g.max_players} · {g.min_playtime}–{g.max_playtime}m
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </div>
      )}
    </main>
  );
}
