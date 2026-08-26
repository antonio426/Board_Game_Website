"use client";

import { useState } from "react";
import { useTranslations } from "next-intl";
import { Link } from "@/i18n/routing";
import GameImage, { gameImageUrl } from "@/components/GameImage";

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8001/api/v1";

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
  bgg_weight: number;
  categories: { name: string }[];
  mechanics: { name: string }[];
}

const STEPS = ["players", "playtime", "weight", "preferences"] as const;

const CATEGORIES = [
  "Thematic", "Strategy", "Party", "Family", "Abstract",
  "Cooperative", "Economic", "Negotiation", "Adventure", "Puzzle",
];

const MECHANICS = [
  "Worker Placement", "Deck Building", "Dice Rolling", "Tile Placement",
  "Auction", "Drafting", "Set Collection", "Area Control", "Hidden Roles",
  "Push Your Luck",
];

export default function SurveyPage() {
  const t = useTranslations("survey");
  const tc = useTranslations("common");
  const [step, setStep] = useState(0);
  const [players, setPlayers] = useState(4);
  const [playtime, setPlaytime] = useState(60);
  const [weight, setWeight] = useState(2.5);
  const [selectedCats, setSelectedCats] = useState<string[]>([]);
  const [selectedMechs, setSelectedMechs] = useState<string[]>([]);
  const [results, setResults] = useState<Game[]>([]);
  const [loading, setLoading] = useState(false);

  const toggleItem = (list: string[], setList: (v: string[]) => void, item: string) => {
    setList(list.includes(item) ? list.filter((i) => i !== item) : [...list, item]);
  };

  const submit = async () => {
    setLoading(true);
    try {
      const params = new URLSearchParams({ top_k: "12", players: String(players), playtime: String(playtime) });
      if (weight < 5) params.set("max_weight", String(weight));
      if (selectedCats.length > 0) params.set("category", selectedCats[0]);
      if (selectedMechs.length > 0) params.set("mechanic", selectedMechs[0]);
      const res = await fetch(`${API_BASE}/recommendations/context?${params}`);
      const data = await res.json();
      setResults(data.recommendations || []);
    } catch { setResults([]); } finally { setLoading(false); setStep(4); }
  };

  const progress = ((step + 1) / (STEPS.length + 1)) * 100;

  if (step === 4) {
    return (
      <main className="mx-auto max-w-4xl px-5 py-8">
        <div className="mb-6 flex items-center gap-3">
          <div className="h-6 w-1 rounded-full" style={{ background: '#D97706' }} />
          <h1 className="font-display text-3xl tracking-wide">{t("resultsTitle")}</h1>
        </div>
        {results.length === 0 ? (
          <p style={{ color: 'var(--color-text-muted)' }}>{tc("noResults")}</p>
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {results.map((g, i) => {
              const name = g.name_zh || g.name_en;
              return (
                <Link key={g.bgg_id} href={`/games/${g.bgg_id}`} className="game-card group relative">
                  {i === 0 && (
                    <div className="absolute top-0 left-0 right-0 flex items-center gap-1.5 px-3 py-1.5 text-xs font-semibold" style={{ background: 'rgba(217,119,6,0.9)', color: '#fff' }}>
                      <svg width="12" height="12" viewBox="0 0 24 24" fill="currentColor"><path d="M12 2l3.09 6.26L22 9.27l-5 4.87 1.18 6.88L12 17.77l-6.18 3.25L7 14.14 2 9.27l6.91-1.01L12 2z"/></svg>
                      {t("bestMatch")}
                    </div>
                  )}
                  <div className="flex gap-3 p-3">
                    <GameImage src={gameImageUrl(g as Record<string, unknown>)} alt={name} className="h-20 w-20 rounded-lg object-cover" />
                    <div className="flex-1 min-w-0">
                      <h3 className="truncate text-sm font-semibold" style={{ color: '#F1F5F9' }}>{name}</h3>
                      <div className="mt-1 text-xs" style={{ color: 'var(--color-text-muted)' }}>
                        ★ {g.bgg_rating} · {g.min_players}–{g.max_players} · {g.min_playtime}–{g.max_playtime}m
                      </div>
                      <div className="mt-1.5 flex flex-wrap gap-1">
                        {g.categories.slice(0, 2).map((c) => <span key={c.name} className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(21,128,61,0.12)', color: '#4ADE80' }}>{c.name}</span>)}
                        {g.mechanics.slice(0, 2).map((m) => <span key={m.name} className="rounded-full px-2 py-0.5 text-[10px] font-medium" style={{ background: 'rgba(217,119,6,0.12)', color: '#FBBF24' }}>{m.name}</span>)}
                      </div>
                    </div>
                  </div>
                </Link>
              );
            })}
          </div>
        )}
        <button onClick={() => { setStep(0); setResults([]); }}
          className="mt-6 rounded-lg px-5 py-2.5 text-sm font-medium transition-colors"
          style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)', color: '#CBD5E1' }}
        >{t("retake")}</button>
      </main>
    );
  }

  return (
    <main className="mx-auto max-w-xl px-5 py-8">
      <div className="mb-6">
        <div className="h-2 rounded-full overflow-hidden" style={{ background: 'var(--color-surface)' }}>
          <div className="h-2 rounded-full transition-all duration-500" style={{ width: `${progress}%`, background: 'linear-gradient(90deg, #15803D, #D97706)' }} />
        </div>
        <p className="mt-2 text-sm" style={{ color: 'var(--color-text-muted)' }}>{t("stepOf", { current: step + 1, total: STEPS.length + 1 })}</p>
      </div>

      <div className="rounded-xl p-6" style={{ background: 'var(--color-surface)', border: '1px solid var(--color-border)' }}>
        {step === 0 && (
          <div>
            <h2 className="mb-6 font-display text-2xl tracking-wide">{t("playersQ")}</h2>
            <div className="flex items-center gap-4">
              <input type="range" min={1} max={10} value={players} onChange={(e) => setPlayers(Number(e.target.value))}
                className="flex-1 accent-[#15803D]" />
              <span className="w-10 text-center text-2xl font-bold" style={{ color: '#4ADE80' }}>{players}</span>
            </div>
            <p className="mt-3 text-sm" style={{ color: 'var(--color-text-secondary)' }}>
              {players <= 2 ? t("playersDuel") : players <= 4 ? t("playersSmall") : t("playersLarge")}
            </p>
          </div>
        )}

        {step === 1 && (
          <div>
            <h2 className="mb-6 font-display text-2xl tracking-wide">{t("playtimeQ")}</h2>
            <div className="grid grid-cols-3 gap-3">
              {[30, 60, 120].map((m) => (
                <button key={m} onClick={() => setPlaytime(m)}
                  className="rounded-xl p-5 text-center transition-all"
                  style={{
                    background: playtime === m ? 'rgba(21,128,61,0.15)' : 'var(--color-muted)',
                    border: `1px solid ${playtime === m ? 'rgba(21,128,61,0.4)' : 'var(--color-border)'}`,
                  }}
                >
                  <div className="text-2xl font-bold" style={{ color: playtime === m ? '#4ADE80' : '#F1F5F9' }}>{m}</div>
                  <div className="text-sm mt-1" style={{ color: 'var(--color-text-muted)' }}>{t("minutes")}</div>
                </button>
              ))}
            </div>
          </div>
        )}

        {step === 2 && (
          <div>
            <h2 className="mb-6 font-display text-2xl tracking-wide">{t("weightQ")}</h2>
            <div className="flex items-center gap-4">
              <input type="range" min={1} max={5} step={0.5} value={weight} onChange={(e) => setWeight(Number(e.target.value))}
                className="flex-1 accent-[#15803D]" />
              <span className="w-10 text-center text-2xl font-bold" style={{ color: '#4ADE80' }}>{weight}</span>
            </div>
            <div className="mt-3 flex justify-between text-sm" style={{ color: 'var(--color-text-muted)' }}>
              <span>{t("light")}</span><span>{t("medium")}</span><span>{t("heavy")}</span>
            </div>
          </div>
        )}

        {step === 3 && (
          <div>
            <h2 className="mb-6 font-display text-2xl tracking-wide">{t("prefQ")}</h2>
            <h3 className="mb-2 text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>{tc("categories")}</h3>
            <div className="mb-5 flex flex-wrap gap-2">
              {CATEGORIES.map((c) => (
                <button key={c} onClick={() => toggleItem(selectedCats, setSelectedCats, c)}
                  className="rounded-full px-3 py-1.5 text-sm font-medium transition-all"
                  style={{
                    background: selectedCats.includes(c) ? '#15803D' : 'var(--color-muted)',
                    color: selectedCats.includes(c) ? '#fff' : '#CBD5E1',
                    border: `1px solid ${selectedCats.includes(c) ? '#15803D' : 'var(--color-border)'}`,
                  }}
                >{c}</button>
              ))}
            </div>
            <h3 className="mb-2 text-sm font-medium" style={{ color: 'var(--color-text-secondary)' }}>{tc("mechanics")}</h3>
            <div className="flex flex-wrap gap-2">
              {MECHANICS.map((m) => (
                <button key={m} onClick={() => toggleItem(selectedMechs, setSelectedMechs, m)}
                  className="rounded-full px-3 py-1.5 text-sm font-medium transition-all"
                  style={{
                    background: selectedMechs.includes(m) ? '#D97706' : 'var(--color-muted)',
                    color: selectedMechs.includes(m) ? '#fff' : '#CBD5E1',
                    border: `1px solid ${selectedMechs.includes(m) ? '#D97706' : 'var(--color-border)'}`,
                  }}
                >{m}</button>
              ))}
            </div>
          </div>
        )}

        <div className="mt-8 flex justify-between">
          {step > 0 ? (
            <button onClick={() => setStep(step - 1)} className="rounded-lg px-5 py-2.5 text-sm font-medium transition-colors"
              style={{ background: 'var(--color-muted)', border: '1px solid var(--color-border)', color: '#CBD5E1' }}
            >{t("back")}</button>
          ) : <div />}
          {step < 3 ? (
            <button onClick={() => setStep(step + 1)} className="rounded-lg px-5 py-2.5 text-sm font-semibold transition-all hover:-translate-y-0.5"
              style={{ background: '#15803D', color: '#fff' }}
            >{t("next")}</button>
          ) : (
            <button onClick={submit} disabled={loading}
              className="rounded-lg px-6 py-2.5 text-sm font-semibold transition-all hover:-translate-y-0.5 disabled:opacity-30"
              style={{ background: '#D97706', color: '#fff' }}
            >{loading ? tc("loading") : t("getResults")}</button>
          )}
        </div>
      </div>
    </main>
  );
}
