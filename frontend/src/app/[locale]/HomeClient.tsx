"use client";

import { useEffect, useState } from "react";
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
  bgg_rating: number;
  min_players: number;
  max_players: number;
  min_playtime: number;
  max_playtime: number;
  recommendation_score?: number;
}

async function fetchGames(path: string): Promise<Game[]> {
  try {
    const data = await apiFetch<{ recommendations?: Game[]; games?: Game[] }>(path);
    return data.recommendations || data.games || [];
  } catch {
    return [];
  }
}

function GameCard({ game, locale }: { game: Game; locale: string }) {
  const name = locale === "zh" ? (game.name_zh || game.name_en) : (game.name_en || game.name_zh);
  return (
    <Link href={`/games/${game.bgg_id}`} className="game-card group block">
      <div className="aspect-[4/3] overflow-hidden" style={{ background: 'var(--color-muted)' }}>
        <GameImage src={gameImageUrl(game)} alt={name} className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-105" />
      </div>
      <div className="p-3.5">
        <h3 className="truncate text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{name}</h3>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          <span className="badge badge-rating">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="#FBBF24"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
            {game.bgg_rating?.toFixed(1)}
          </span>
          <span className="badge badge-players">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#60A5FA" strokeWidth="2"><circle cx="9" cy="7" r="3"/><path d="M5 21v-2a4 4 0 014-4"/></svg>
            {game.min_players}-{game.max_players}P
          </span>
          <span className="badge badge-time">
            <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="#A78BFA" strokeWidth="2"><circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/></svg>
            {game.min_playtime}-{game.max_playtime}m
          </span>
        </div>
      </div>
    </Link>
  );
}

function QuickLink({ href, onClick, color, icon, label, desc }: { href?: string; onClick?: () => void; color: string; icon: React.ReactNode; label: string; desc?: string }) {
  const content = (
    <>
      <div className="absolute inset-0 opacity-0 transition-opacity duration-300 group-hover:opacity-100" style={{ background: `radial-gradient(circle at 50% 50%, ${color}12, transparent 70%)` }} />
      <div className="relative">
        <div className="mb-3 flex h-10 w-10 items-center justify-center" style={{ background: `${color}15`, borderRadius: 'var(--radius-md)' }}>
          {icon}
        </div>
        <h3 className="text-sm font-semibold" style={{ color: 'var(--color-text-primary)' }}>{label}</h3>
        {desc && <p className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>{desc}</p>}
      </div>
    </>
  );
  const cls = "group relative overflow-hidden p-5 text-left transition-all hover:-translate-y-0.5";
  const style = { background: 'var(--color-surface)', border: '1px solid var(--color-border)', borderRadius: 'var(--radius-xl)' };
  if (onClick) {
    return <button type="button" onClick={onClick} className={cls} style={style}>{content}</button>;
  }
  return <Link href={href!} className={cls + " block"} style={style}>{content}</Link>;
}

function SectionHeader({ color, title }: { color: string; title: string }) {
  return (
    <div className="mb-5 flex items-center gap-3">
      <div className="section-bar" style={{ background: color }} />
      <h2 className="font-display text-xl tracking-wide" style={{ color: 'var(--color-text-primary)' }}>{title}</h2>
    </div>
  );
}

export default function HomeClient() {
  const t = useTranslations("home");
  const locale = useLocale();
  const router = useRouter();
  const [topRated, setTopRated] = useState<Game[]>([]);
  const [forYou, setForYou] = useState<Game[]>([]);
  const [quickPicks, setQuickPicks] = useState<Game[]>([]);

  const goRandom = async () => {
    try {
      const res = await apiFetch<{ bgg_id: number }>("/games/random");
      if (res?.bgg_id) router.push(`/games/${res.bgg_id}`);
    } catch {}
  };

  useEffect(() => {
    (async () => {
      const [rated, recs, quick] = await Promise.all([
        fetchGames("/games?sort_by=bgg_rating&sort_order=desc&per_page=6"),
        fetchGames("/recommendations/for-me?top_k=6"),
        fetchGames("/recommendations/context?players=4&playtime=60&top_k=6"),
      ]);
      setTopRated(rated);
      setForYou(recs);
      setQuickPicks(quick);
    })();
  }, []);

  return (
    <div className="mx-auto max-w-7xl px-5 py-10 space-y-12">
      {forYou.length > 0 && (
        <section>
          <SectionHeader color="#D97706" title={t("forYou")} />
          <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
            {forYou.map((g) => <GameCard key={g.bgg_id} game={g} locale={locale} />)}
          </div>
        </section>
      )}

      <section>
        <SectionHeader color="#4ADE80" title={t("topRated")} />
        <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
          {topRated.map((g) => <GameCard key={g.bgg_id} game={g} locale={locale} />)}
        </div>
      </section>

      <section>
        <SectionHeader color="#A78BFA" title={t("quickPicks")} />
        <div className="grid gap-4 grid-cols-2 sm:grid-cols-3 lg:grid-cols-6">
          {quickPicks.map((g) => <GameCard key={g.bgg_id} game={g} locale={locale} />)}
        </div>
      </section>

      <section>
        <SectionHeader color="#60A5FA" title="Quick Start" />
        <div className="grid gap-4 sm:grid-cols-3">
          <QuickLink
            href="/games?min_players=2"
            color="#D97706"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#FBBF24" strokeWidth="1.5"><circle cx="9" cy="7" r="3"/><circle cx="15" cy="7" r="3"/><path d="M5 21v-2a4 4 0 014-4h0M19 21v-2a4 4 0 00-4-4h0"/></svg>}
            label={t("quick2p")}
          />
          <QuickLink
            href="/games?min_players=4&max_playtime=60"
            color="#15803D"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#4ADE80" strokeWidth="1.5"><rect x="3" y="3" width="7" height="7" rx="1"/><rect x="14" y="3" width="7" height="7" rx="1"/><rect x="3" y="14" width="7" height="7" rx="1"/><rect x="14" y="14" width="7" height="7" rx="1"/></svg>}
            label={t("quickParty")}
          />
          <QuickLink
            href="/games?max_weight=2&max_playtime=30"
            color="#7C3AED"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#A78BFA" strokeWidth="1.5"><path d="M13 2L3 14h9l-1 8 10-12h-9l1-8z"/></svg>}
            label={t("quickLight")}
          />
          <QuickLink
            onClick={goRandom}
            color="#22C55E"
            icon={<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#22C55E" strokeWidth="1.5"><rect x="3" y="3" width="18" height="18" rx="2"/><circle cx="8" cy="8" r="1.5"/><circle cx="16" cy="16" r="1.5"/><circle cx="16" cy="8" r="1.5"/><circle cx="8" cy="16" r="1.5"/></svg>}
            label={t("feelingLucky")}
            desc="Discover a random board game"
          />
        </div>
      </section>
    </div>
  );
}
