# CLAUDE.md — Board Game Explorer

Bilingual (zh-TW / en) board game discovery platform. Product goal: a user arrives without
knowing what they want, and leaves with 3–5 games they will actually buy or play. Everything
below is in service of **search → filter → recommend**.

## Stack

| Layer | Tech | Notes |
|---|---|---|
| Frontend | Next.js 16 (App Router) + next-intl + Tailwind v4 | `frontend/`, locale routes under `src/app/[locale]/` |
| Backend | FastAPI (Python) | `backend/app/`, routers under `app/api/v1/` |
| Primary DB | MongoDB 7 (`boardgame.board_games`) | 180,401 docs, ~89 MB |
| Vector DB | Qdrant (`board_games` collection) | `BAAI/bge-small-en-v1.5` via fastembed, 384-dim |
| Cache | Redis 7 | 120–300 s TTL on list/search/recommendation responses |

## Commands

```bash
docker compose up -d                       # mongo 27017, qdrant 6333, redis 6379
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload   # :8000
cd frontend && npm run dev                 # :3000
cd frontend && npx tsc --noEmit && npm run lint    # required before commit
cd backend && .venv/bin/python scripts/data_health.py          # field coverage after any crawl
cd backend && .venv/bin/python scripts/ensure_indexes.py       # idempotent, also runs at startup
cd backend && .venv/bin/python scripts/compute_quality_score.py  # after any rating refresh
cd backend && .venv/bin/python scripts/backfill_dynamicinfo.py   # weight, polls, ranks (resumable)
cd backend && .venv/bin/python scripts/mark_expansions.py        # is_expansion from rank data
cd backend && .venv/bin/python scripts/index_embeddings.py --recreate  # rebuild Qdrant vectors
python3 -c "import json;[json.load(open(f)) for f in ('frontend/src/i18n/en.json','frontend/src/i18n/zh.json')]"
```

Mongo shell:

```bash
docker exec $(docker ps -qf name=mongodb) mongosh -u boardgame -p boardgame_dev --quiet \
  --eval 'db.getSiblingDB("boardgame").board_games.countDocuments({})'
```

## Data model — `board_games`

Fields present on every doc: `bgg_id`, `name_en`, `name_zh`, `description_en`, `description_zh`,
`bgg_rank`, `bgg_rating`, `bgg_avg_rating`, `bgg_weight`, `users_rated`, `min_players`,
`max_players`, `min_playtime`, `max_playtime`, `min_age`, `year_published`, `categories[]`,
`mechanics[]`, `designers[]`, `publishers[]`, `image`, `thumbnail`, `local_image`,
`local_thumbnail`, `aliases[]`, `is_expansion`, `series`, `expansions`, `subcategory_ranks`.

Written by the Phase 1-2 scripts: `quality_score` (Bayesian rating, see
`scripts/compute_quality_score.py`), `bgg_weight` + `bgg_weight_votes`, `best_players[]`,
`recommended_players[]`, `language_dependence`, `player_age`, `subcategory_ranks[]` and
`dynamicinfo_at` (`scripts/backfill_dynamicinfo.py`), `subtype` + `subtype_at`
(`scripts/backfill_subtypes.py`).

`categories` / `mechanics` are objects: `{id, name, name_zh}`. 85 categories, 196 mechanics.

### Field coverage (measured before the Phase 1 backfills; re-run `scripts/data_health.py`)

| Field | Docs with usable value | Consequence |
|---|---|---|
| `description_en` non-empty | 43,401 | The de-facto "real game" filter used by every endpoint |
| `bgg_rating > 0` | 43,474 | Bayesian rank rating; only ranked games have it |
| `bgg_avg_rating > 0` | 140,604 | Raw average; wider coverage, no vote-count weighting |
| `users_rated >= 100` | 23,363 | Best available popularity signal |
| `users_rated >= 1000` | 5,155 | The realistic "recommendable" core |
| `name_zh` non-empty | 3,280 | zh locale falls back to English for most games |
| `description_zh` non-empty | 14 | zh descriptions are effectively missing |
| `bgg_weight > 0` | 9 | **Complexity is not populated** |
| `aliases` present | 3,280 | CJK alias search only covers translated games |
| Qdrant vectors | 7,833 | Semantic search covers ~18 % of quality games |

### Known traps

- **Semantic search is English-only.** `BAAI/bge-small-en-v1.5` is a retrieval model; a
  multilingual paraphrase model was tried first and retrieved far worse ("birds engine builder"
  returned five games with Birds in the title and no Wingspan). Chinese queries go through the
  lexical path, which matches `name_zh` and `aliases`. `SEMANTIC_SEARCH_ENABLED=false` turns the
  vector path off entirely and avoids the model download at boot.
- **Two vocabularies exist for players and playtime.** `players`, `playtime_max` and
  `playtime_min` mean what they say. The older `min_players`, `max_players`, `min_playtime` and
  `max_playtime` are single-sided range-overlap tests — `max_playtime=30` means "its ceiling is at
  least 30 minutes" — kept only for compatibility. Use the first set.
- **`bgg_weight` is being backfilled.** Until `scripts/backfill_dynamicinfo.py` finishes its sweep,
  complexity filters only see the games already covered; check with `scripts/data_health.py`.
- **The BGG XML API answers 401 now.** Crawlers use `api.geekdo.com/api/dynamicinfo` (weight,
  player polls, subdomain ranks) and `api.geekdo.com/api/geekitems` (real subtype). That API
  starts returning 429 above roughly ten requests a second across all jobs, so keep
  `CONCURRENCY` low and never run both sweeps at once.
- **`bgg_rank` is populated for all 180 k docs**, including 155 k with rank > 25 000, and the head
  of the list has ties (rank 2 is both Ark Nova and a game with `users_rated = 0`). Sorting by
  rank is meaningful only near the top.
- Some `categories` / `mechanics` array entries have a null `name` (Splendor's categories render
  as `,,`). The tag list endpoints filter these out; the underlying docs still carry them.
- `name_zh` used to hold Japanese titles on 641 games (Catan = カタン, Ticket to Ride = 乗車券).
  `scripts/clean_zh_names.py` moved those into `aliases` and cleared the field, so zh falls back
  to the English name instead of showing Japanese. Re-run it after any enricher pass — the
  enrichers still accept any CJK alternate BGG offers.
- `description_zh` exists as an empty string on every doc — presence checks must test `$ne: ""`,
  not `$exists`.
- Fixed in Phase 0, kept here as history: the code used to query a `num_ratings` field that does
  not exist (real name `users_rated`), which silently disabled the `min_ratings` filter and the
  zh-locale quality gate.

## Core modules

- `app/core/quality.py` is the only place that decides what is showable: `QUALITY_FILTER`
  (`description_en` non-empty), `quality_gate(locale, min_users_rated)` which adds the zh rule
  (`bgg_rating >= 6 OR users_rated >= 50`, 25,466 docs), `is_low_quality(doc, locale)`, and
  `merge_filters(*fragments)` which combines filters without one `$or` clobbering another.
  Never re-inline the `description_en` check.
- `app/core/indexes.py` holds the 10 `board_games` indexes; `ensure_indexes()` runs on app
  startup and via `scripts/ensure_indexes.py`. Any new filter field needs an index here.
- `app/core/tags.py::tag_filter(field, value)` canonicalizes a category or mechanic name against
  the cached vocabulary (85 + 196 names, 10 min TTL) so the filter is an indexed equality match
  instead of a case-insensitive regex — worth ~230 ms per request. It falls back to regex for
  values that are not real tag names.
- `app/core/filters.py::build_filters(...)` turns request parameters into one Mongo filter, shared
  by the list, search and facet endpoints so a chip's count always matches the page behind it.
  `BASE_GAMES_ONLY` excludes expansions, which is the default everywhere.
- `app/core/search.py` owns name matching and ranking: `build_name_query` (CJK variants across
  `name_en`/`name_zh`/`aliases`), `relevance` (exact 100 > prefix 60 > word 40 > substring 20,
  minus 25 for an expansion, plus `quality_score`), `paged_search`, and `rerank_semantic`, which
  blends cosine similarity 0.65 / quality 0.20 / log-scaled audience size 0.15 — without the last
  two, short documents that echo the query outrank the games people mean.
- `app/recommenders/diversity.py::diversify` re-ranks a scored list with MMR (λ 0.7) and caps two
  per series and two per designer, so "similar to Catan" stops being five Catan editions.

## Search quality harness

`tests/golden_queries.json` holds 33 graded queries; `scripts/eval_search.py` scores recall@10,
top-1 accuracy, and condition precision against a running API. Run it before and after any change
to ranking, filtering, or the quality gate:

```bash
cd backend && .venv/bin/python scripts/eval_search.py --base http://localhost:8000/api/v1
cd backend && .venv/bin/python scripts/eval_search.py --compare tests/eval_baseline.json
```

`tests/eval_baseline.json` holds the current run — 37 cases, all passing. For reference, the
Phase 0 starting point was `recall@10 84.2%, top1 66.7%, precision@10 84.3%, 4 zero-result cases`.

A failing case is usually a real regression, but check coverage first: semantic cases need the
Qdrant index built (`scripts/index_embeddings.py`), and complexity cases need `bgg_weight`.

## Defaults worth knowing

- Sort defaults to `quality` (`quality_score`, Bayesian with m=1000), not `bgg_rank`.
- Expansions are excluded unless `include_expansions=true`: they outscore the base games they
  extend, so an unfiltered top ten was mostly Spirit Island and Ark Nova expansions.
  `is_expansion` comes from `bgg_rank == 99999` plus at least 30 ratings — BGG ranks every rated
  base game and never ranks an expansion — which agreed with the authoritative subtype API on all
  3,296 games where both were known. `scripts/mark_expansions.py` applies it offline.
- The zh locale additionally hides games below `bgg_rating 6` with fewer than 50 ratings.
- Recommendation fallback chain: collaborative (needs 5+ interactions) → content similarity →
  taste profile → `quality_score` leaderboard. Nothing returns an empty list.

## API surface

- `GET /api/v1/games` — paged list. `players`, `best_at_players`, `playtime_max`, `playtime_min`,
  `min_rating`, `min_weight`/`max_weight`, `category`, `mechanic`, `q`, `include_expansions`,
  `sort` ∈ quality|rating|rank|name|weight|year.
- `GET /api/v1/games/search` — everything above plus comma-separated `categories`, `mechanics`,
  `designers`, `publishers`, `categories_mode`/`mechanics_mode` (`any` = `$in`, `all` = `$all`),
  `exclude_categories`, `exclude_mechanics`, `min_ratings`, and `semantic=true`.
- `GET /api/v1/games/facets` — the same filter parameters, returning how many games each remaining
  option would leave (tags, player counts, playtime and weight bands).
- `GET /api/v1/games/{bgg_id}`, `/games/random`, `/games/categories`, `/games/mechanics`.
- `GET /api/v1/recommendations/similar/{bgg_id}?method=content|collaborative|hybrid&diverse=true`
  — each result carries `reasoning.matched_categories` / `matched_mechanics`.
- `POST /api/v1/recommendations/preferences` — cold start from survey answers.
- `GET /api/v1/recommendations/for-me`, `/context`, `/semantic`, `POST /index`.
- `POST /api/v1/chat/recommend` — keyword advisor; pass `session_id` back to keep the accumulated
  constraints (stored in Redis for 30 minutes).

Recommenders live in `app/recommenders/`: `content_based.py` (sparse tag-set similarity over the
recommendable corpus, returns the overlap it scored with), `collaborative.py` (item-item cosine
over `user_actions`, built in memory at first call), `hybrid.py` (blend plus fallback chain),
`diversity.py` (MMR), `embedding.py` (fastembed + Qdrant).

Collaborative filtering has 15 `user_actions` rows and 0 users — it returns nothing in practice.
Treat content-based plus popularity as the only live ranking signals today.

## Conventions

- Search is CJK-aware: `app/core/cjk.py::expand_query_variants` produces simplified/traditional
  variants; every name query must OR over `name_en`, `name_zh`, and `aliases`.
- Write path stores Traditional Chinese; enrichers also append to `aliases`.
- All list responses share the envelope `{games, total, page, per_page, total_pages}`.
- Images resolve to `/images/{bgg_id}.jpg` and `/thumbnails/{bgg_id}.jpg` served by FastAPI
  static mounts; `_format_game` fills these in when the DB fields are absent.
- Locale handling belongs in `_format_game` (`display_name`), not in components.
- i18n keys live in `frontend/src/i18n/{en,zh}.json` — both files must stay in sync.
- Design system: `design-system/boardgamehub/MASTER.md` (felt green + gold on dark,
  Righteous + Poppins).

## Working agreements

- Prefer fixing a data-coverage problem over adding a UI control that filters on an empty field.
- Any new filter needs a matching Mongo index and a measured `explain()` before it ships.
- Verify with `tsc --noEmit`, `npm run lint`, both i18n JSON files parsing, and a manual
  happy-path plus one edge case in the browser.
- Roadmaps live in `docs/`: `UX_ROADMAP.md` (page-level UX), `SEARCH_DISCOVERY_PLAN.md`
  (search, filtering, and recommendation quality).
