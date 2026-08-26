import { apiFetch } from "@/lib/api";
import GameDetailClient from "./GameDetailClient";

interface Game {
  bgg_id: number;
  name_en: string;
  name_zh: string;
  description_en: string;
  description_zh: string;
  image: string;
  thumbnail: string;
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
  categories: { id: number; name: string }[];
  mechanics: { id: number; name: string }[];
  expansions: { bgg_id: number; name: string }[];
  series: { bgg_id: number; name: string }[];
  designers: string[];
  publishers: string[];
  recommendation_score?: number;
}

interface RecResponse {
  recommendations: Game[];
}

export default async function GameDetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  let game: Game | null = null;
  let similarGames: Game[] = [];

  try {
    game = await apiFetch<Game>(`/games/${id}`);
  } catch {
  }

  if (!game || ("error" in game && (game as { error: string }).error === "not_found")) {
    return (
      <main className="mx-auto max-w-4xl px-5 py-20 text-center">
        <div className="mx-auto mb-4 flex h-16 w-16 items-center justify-center rounded-2xl" style={{ background: 'rgba(217,119,6,0.12)' }}>
          <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="#FBBF24" strokeWidth="1.5"><circle cx="12" cy="12" r="10"/><path d="M16 16s-1.5-2-4-2-4 2-4 2"/><line x1="9" y1="9" x2="9.01" y2="9"/><line x1="15" y1="9" x2="15.01" y2="9"/></svg>
        </div>
        <h1 className="font-display text-2xl tracking-wide">Game not found</h1>
      </main>
    );
  }

  try {
    const recData = await apiFetch<RecResponse>(`/recommendations/similar/${id}?top_k=6&method=hybrid`);
    similarGames = recData.recommendations || [];
  } catch {
  }

  return <GameDetailClient game={game} similarGames={similarGames} />;
}
