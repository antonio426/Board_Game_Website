"use client";

import { useEffect, useState } from "react";
import { useTranslations, useLocale } from "next-intl";
import { useSearchParams } from "next/navigation";
import { Link } from "@/i18n/routing";
import GameImage, { gameImageUrl } from "@/components/GameImage";
import { useCompare } from "@/hooks/useCompare";
import { apiFetch } from "@/lib/api";

interface Tag {
  id?: number;
  name: string;
  name_zh?: string;
}

interface CompareGame {
  bgg_id: number;
  display_name?: string;
  name_en: string;
  name_zh: string;
  local_thumbnail?: string;
  local_image?: string;
  bgg_rating: number;
  users_rated?: number;
  bgg_weight: number;
  min_players: number;
  max_players: number;
  best_players?: number[];
  min_playtime: number;
  max_playtime: number;
  min_age: number;
  year_published: number;
}

interface CompareResponse {
  games: CompareGame[];
  shared: { categories: Tag[]; mechanics: Tag[] };
  unique: Record<string, { categories: Tag[]; mechanics: Tag[] }>;
}

const EMPTY: CompareResponse = { games: [], shared: { categories: [], mechanics: [] }, unique: {} };

function tagLabel(tag: Tag, locale: string) {
  return locale === "zh" ? tag.name_zh || tag.name : tag.name;
}

/** A row of the table, with the winning cell picked out. */
function Row({
  label,
  values,
  best,
}: {
  label: string;
  values: string[];
  best?: number;
}) {
  return (
    <tr style={{ borderTop: "1px solid var(--color-border)" }}>
      <th className="py-3 pr-4 text-left text-xs font-medium align-top" style={{ color: "var(--color-text-muted)" }}>
        {label}
      </th>
      {values.map((value, index) => (
        <td
          key={index}
          className="py-3 pr-4 text-sm align-top"
          style={{ color: index === best ? "#4ADE80" : "#E2E8F0", fontWeight: index === best ? 600 : 400 }}
        >
          {value}
        </td>
      ))}
    </tr>
  );
}

/** Index of the highest value, or undefined when nothing stands out. */
function leader(values: number[]): number | undefined {
  const best = Math.max(...values);
  if (!Number.isFinite(best) || best <= 0) return undefined;
  return values.filter((value) => value === best).length === 1 ? values.indexOf(best) : undefined;
}

export default function ComparePage() {
  const t = useTranslations("compare");
  const tc = useTranslations("common");
  const locale = useLocale();
  const searchParams = useSearchParams();
  const { ids: storedIds, toggle } = useCompare();

  // The URL wins, so a comparison can be shared or bookmarked; the stored
  // selection is what the visitor built up while browsing.
  const idsParam = searchParams.get("ids");
  const ids = idsParam ? idsParam.split(",").map(Number).filter(Boolean) : storedIds;

  // One piece of state holding the answer *and* the question it answers, so
  // "still loading" is a comparison rather than a second flag that has to be
  // set synchronously inside the effect.
  const [loaded, setLoaded] = useState<{ key: string; response: CompareResponse }>({ key: "", response: EMPTY });

  const key = ids.join(",");
  const requestKey = `${key}|${locale}`;

  useEffect(() => {
    if (!key) return;
    let active = true;
    (async () => {
      try {
        const response = await apiFetch<CompareResponse>(`/games/compare?ids=${key}&locale=${locale}`);
        if (active) setLoaded({ key: `${key}|${locale}`, response });
      } catch {
        if (active) setLoaded({ key: `${key}|${locale}`, response: EMPTY });
      }
    })();
    return () => {
      active = false;
    };
  }, [key, locale]);

  const data = loaded.key === requestKey ? loaded.response : EMPTY;
  const loading = Boolean(key) && loaded.key !== requestKey;
  const games = data.games;

  if (!key) {
    return (
      <main className="mx-auto max-w-2xl px-5 py-20 text-center">
        <h1 className="font-display text-2xl tracking-wide">{t("title")}</h1>
        <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>{t("empty")}</p>
        <Link href="/games" className="mt-6 inline-block rounded-lg px-6 py-2.5 text-sm font-semibold" style={{ background: "#D97706", color: "#fff" }}>
          {t("browse")}
        </Link>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-6xl px-5 py-8">
      <h1 className="font-display text-2xl tracking-wide">{t("title")}</h1>

      {loading && games.length === 0 ? (
        <p className="mt-6 text-sm" style={{ color: "var(--color-text-muted)" }}>{tc("loading")}</p>
      ) : (
        <>
          <div className="mt-6 overflow-x-auto">
            <table className="w-full min-w-[640px] border-collapse">
              <thead>
                <tr>
                  <th className="w-32" />
                  {games.map((game) => (
                    <th key={game.bgg_id} className="pb-4 pr-4 text-left align-top">
                      <Link href={`/games/${game.bgg_id}`} className="block">
                        <div className="mb-2 h-24 w-24 overflow-hidden rounded-lg" style={{ background: "var(--color-muted)" }}>
                          <GameImage src={gameImageUrl(game)} alt={game.display_name || game.name_en} className="h-full w-full object-cover" />
                        </div>
                        <span className="text-sm font-semibold" style={{ color: "#F1F5F9" }}>
                          {game.display_name || game.name_en}
                        </span>
                      </Link>
                      <button
                        type="button"
                        onClick={() => toggle(game.bgg_id)}
                        className="mt-1 text-xs"
                        style={{ color: "var(--color-text-muted)" }}
                      >
                        {t("remove")}
                      </button>
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                <Row
                  label={tc("rating")}
                  values={games.map((game) => `★ ${game.bgg_rating?.toFixed(2) ?? "-"}`)}
                  best={leader(games.map((game) => game.bgg_rating || 0))}
                />
                <Row
                  label={tc("ratedBy")}
                  values={games.map((game) => (game.users_rated ? game.users_rated.toLocaleString() : "-"))}
                  best={leader(games.map((game) => game.users_rated || 0))}
                />
                <Row
                  label={tc("players")}
                  values={games.map((game) =>
                    game.best_players?.length
                      ? `${game.min_players}–${game.max_players} (${tc("bestAt")} ${game.best_players.join(", ")})`
                      : `${game.min_players}–${game.max_players}`,
                  )}
                />
                <Row
                  label={tc("playtime")}
                  values={games.map((game) => `${game.min_playtime}–${game.max_playtime}m`)}
                />
                <Row
                  label={tc("weight")}
                  values={games.map((game) => (game.bgg_weight ? `${game.bgg_weight.toFixed(1)}/5` : "-"))}
                />
                <Row label={t("minAge")} values={games.map((game) => (game.min_age ? `${game.min_age}+` : "-"))} />
                <Row label={tc("year")} values={games.map((game) => String(game.year_published || "-"))} />
                <Row
                  label={t("uniqueTags")}
                  values={games.map((game) => {
                    const own = data.unique[String(game.bgg_id)];
                    const tags = [...(own?.categories || []), ...(own?.mechanics || [])];
                    return tags.length ? tags.map((tag) => tagLabel(tag, locale)).join("、") : "-";
                  })}
                />
              </tbody>
            </table>
          </div>

          <section className="mt-8">
            <h2 className="font-display text-lg tracking-wide">{t("shared")}</h2>
            {data.shared.categories.length + data.shared.mechanics.length === 0 ? (
              <p className="mt-2 text-sm" style={{ color: "var(--color-text-muted)" }}>{t("noShared")}</p>
            ) : (
              <div className="mt-3 flex flex-wrap gap-2">
                {[...data.shared.categories, ...data.shared.mechanics].map((tag) => (
                  <span
                    key={tag.name}
                    className="rounded-full px-3 py-1 text-xs"
                    style={{ background: "rgba(21,128,61,0.12)", border: "1px solid rgba(21,128,61,0.3)", color: "#4ADE80" }}
                  >
                    {tagLabel(tag, locale)}
                  </span>
                ))}
              </div>
            )}
          </section>
        </>
      )}
    </main>
  );
}
