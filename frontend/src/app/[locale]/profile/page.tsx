"use client";

import { useEffect, useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import { useAuth } from "@/hooks/useAuth";
import GameImage, { gameImageUrl } from "@/components/GameImage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

interface CollectionItem {
  bgg_id: number;
  action_type: string;
  rating: number | null;
  added_at: string;
  game: {
    bgg_id: number;
    name_en: string;
    name_zh: string;
    thumbnail: string;
    local_thumbnail?: string;
    local_image?: string;
    image?: string;
    bgg_rating: number;
    min_players: number;
    max_players: number;
  } | null;
}

export default function ProfilePage() {
  const t = useTranslations("profile");
  const tc = useTranslations("common");
  const nav = useTranslations("nav");
  const { user, loading: authLoading } = useAuth();
  const [items, setItems] = useState<CollectionItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!user) { setLoading(false); return; }
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/actions/collection/me`, { credentials: "include" });
        const data = await res.json();
        setItems(data.items || []);
      } catch {} finally { setLoading(false); }
    })();
  }, [user]);

  if (authLoading) return <main className="p-8"><p>{tc("loading")}</p></main>;

  if (!user) {
    return (
      <main className="mx-auto max-w-2xl px-5 py-20 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl" style={{ background: 'rgba(21,128,61,0.12)' }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" strokeWidth="1.5"><path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/><circle cx="12" cy="7" r="4"/></svg>
        </div>
        <h1 className="font-display text-2xl tracking-wide">{t("loginRequired")}</h1>
        <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>{t("loginHint")}</p>
      </main>
    );
  }

  const favorites = items.filter((i) => i.action_type === "favorite");
  const owned = items.filter((i) => i.action_type === "own");
  const rated = items.filter((i) => i.action_type === "rate" && i.rating);

  return (
    <main className="mx-auto max-w-5xl px-5 py-8">
      <div className="mb-8 flex items-center gap-4">
        {user.avatarUrl && <img src={user.avatarUrl} alt="" className="h-14 w-14 rounded-full" style={{ border: '2px solid var(--color-border)' }} />}
        <div>
          <h1 className="font-display text-2xl tracking-wide">{user.displayName}</h1>
          <p className="text-sm" style={{ color: 'var(--color-text-muted)' }}>{user.email}</p>
        </div>
      </div>

      {loading ? <p>{tc("loading")}</p> : (
        <div className="space-y-8">
          {favorites.length > 0 && (
            <section>
              <h2 className="mb-3 flex items-center gap-2 font-display text-xl tracking-wide">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#F87171" stroke="#F87171" strokeWidth="2"><path d="M20.84 4.61a5.5 5.5 0 00-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 00-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 000-7.78z"/></svg>
                {t("favorites")} ({favorites.length})
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {favorites.map((it) => it.game && (
                  <Link key={it.bgg_id} href={`/games/${it.bgg_id}`}
                    className="flex items-center gap-3 rounded-xl p-3 transition-colors hover:bg-white/[0.03]"
                    style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
                  >
                    <GameImage src={gameImageUrl(it.game as Record<string, unknown>)} alt={it.game.name_en} className="h-14 w-14 rounded-lg object-cover" />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#F1F5F9' }}>{it.game.name_zh || it.game.name_en}</div>
                      <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>★ {it.game.bgg_rating} · {it.game.min_players}-{it.game.max_players}</div>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {owned.length > 0 && (
            <section>
              <h2 className="mb-3 flex items-center gap-2 font-display text-xl tracking-wide">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" strokeWidth="2"><path d="M21 16V8a2 2 0 00-1-1.73l-7-4a2 2 0 00-2 0l-7 4A2 2 0 003 8v8a2 2 0 001 1.73l7 4a2 2 0 002 0l7-4A2 2 0 0021 16z"/></svg>
                {t("ownedGames")} ({owned.length})
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {owned.map((it) => it.game && (
                  <Link key={it.bgg_id} href={`/games/${it.bgg_id}`}
                    className="flex items-center gap-3 rounded-xl p-3 transition-colors hover:bg-white/[0.03]"
                    style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
                  >
                    <GameImage src={gameImageUrl(it.game as Record<string, unknown>)} alt={it.game.name_en} className="h-14 w-14 rounded-lg object-cover" />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#F1F5F9' }}>{it.game.name_zh || it.game.name_en}</div>
                      <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>★ {it.game.bgg_rating}</div>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {rated.length > 0 && (
            <section>
              <h2 className="mb-3 flex items-center gap-2 font-display text-xl tracking-wide">
                <svg width="18" height="18" viewBox="0 0 24 24" fill="#FBBF24" stroke="#FBBF24" strokeWidth="2"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                {t("myRatings")} ({rated.length})
              </h2>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                {rated.map((it) => it.game && (
                  <Link key={it.bgg_id} href={`/games/${it.bgg_id}`}
                    className="flex items-center gap-3 rounded-xl p-3 transition-colors hover:bg-white/[0.03]"
                    style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}
                  >
                    <GameImage src={gameImageUrl(it.game as Record<string, unknown>)} alt={it.game.name_en} className="h-14 w-14 rounded-lg object-cover" />
                    <div>
                      <div className="text-sm font-semibold" style={{ color: '#F1F5F9' }}>{it.game.name_zh || it.game.name_en}</div>
                      <div className="text-xs" style={{ color: 'var(--color-text-muted)' }}>My: {it.rating}/10 · BGG: ★ {it.game.bgg_rating}</div>
                    </div>
                  </Link>
                ))}
              </div>
            </section>
          )}

          {items.length === 0 && (
            <div className="py-16 text-center">
              <p style={{ color: 'var(--color-text-muted)' }}>{t("emptyCollection")}</p>
              <Link href="/games" className="mt-4 inline-block rounded-lg px-6 py-2.5 text-sm font-semibold transition-all hover:-translate-y-0.5" style={{ background: '#D97706', color: '#fff' }}>{nav("games")}</Link>
            </div>
          )}
        </div>
      )}
    </main>
  );
}
