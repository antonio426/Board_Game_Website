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
| Vector DB | Qdrant (`board_games` collection) | 7,833 points only |
| Cache | Redis 7 | 120–300 s TTL on list/search/recommendation responses |

## Commands

```bash
docker compose up -d                       # mongo 27017, qdrant 6333, redis 6379
cd backend && source .venv/bin/activate && uvicorn app.main:app --reload   # :8000
cd frontend && npm run dev                 # :3000
cd frontend && npx tsc --noEmit && npm run lint    # required before commit
cd backend && .venv/bin/python scripts/data_health.py       # field coverage after any crawl
cd backend && .venv/bin/python scripts/ensure_indexes.py    # idempotent, also runs at startup
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

`categories` / `mechanics` are objects: `{id, name, name_zh}`. 85 categories, 196 mechanics.

### Field coverage (measured, keep this honest)

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

- **Semantic search is not semantic.** `app/recommenders/embedding.py::_text_to_vector` hashes
  the text with SHA-256 and spreads the bytes through `sin()`; it is a placeholder, not an
  embedding model, so Qdrant returns unrelated games. The path is gated behind
  `SEMANTIC_SEARCH_ENABLED` (default `false`) and callers fall back to lexical search. Turn it on
  only after a real model replaces `_text_to_vector`.
- **Playtime and player filters mean the opposite of what the UI implies.** `max_playtime=30`
  compiles to `max_playtime >= 30` ("its ceiling is at least 30 min"), and `min_players=4` to
  `min_players <= 4`. Each is a single-sided range-overlap test, not "games that fit in 30
  minutes" or "games for 4 players". Fixing the semantics is plan item P3.4.
- **`bgg_weight` is empty** (9 docs), so `min_weight` / `max_weight` filters and the weight
  dimension of `ContentBasedRecommender` do nothing until the backfill lands.
- **`bgg_rank` is populated for all 180 k docs**, including 155 k with rank > 25 000, and the head
  of the list has ties (rank 2 is both Ark Nova and a game with `users_rated = 0`). Sorting by
  rank is meaningful only near the top.
- Some `categories` / `mechanics` array entries have a null `name` (Splendor's categories render
  as `,,`). The tag list endpoints filter these out; the underlying docs still carry them.
- Many `name_zh` values are Japanese, not Chinese (Catan = カタン, Ticket to Ride = 乗車券), so
  "has `name_zh`" is not the same as "has a Chinese name".
- `description_zh` exists as an empty string on every doc — presence checks must test `$ne: ""`,
  not `$exists`.
- Fixed in Phase 0, kept here as history: the code used to query a `num_ratings` field that does
  not exist (real name `users_rated`), which silently disabled the `min_ratings` filter and the
  zh-locale quality gate.

## Quality gate, indexes, tags

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

## Search quality harness

`tests/golden_queries.json` holds 33 graded queries; `scripts/eval_search.py` scores recall@10,
top-1 accuracy, and condition precision against a running API. Run it before and after any change
to ranking, filtering, or the quality gate:

```bash
cd backend && .venv/bin/python scripts/eval_search.py --base http://localhost:8000/api/v1
cd backend && .venv/bin/python scripts/eval_search.py --compare tests/eval_baseline.json
```

Baseline after Phase 0 (`tests/eval_baseline.json`):
`recall@10 84.2%, top1 66.7%, precision@10 84.3%, 4 zero-result cases`.

## API surface

- `GET /api/v1/games` — paged list, filters (`min_players`, `max_playtime`, `min_rating`,
  `min_weight`/`max_weight`, `category`, `mechanic`, `q`), `sort` ∈ rating|rank|name|weight|year.
  Single-value category/mechanic, matched by case-insensitive `$regex`.
- `GET /api/v1/games/search` — accepts comma-separated `categories`, `mechanics`, `designers`,
  `publishers` (`$in`), plus `semantic=true` to route through Qdrant with a regex fallback.
- `GET /api/v1/games/{bgg_id}`, `/games/random`, `/games/categories`, `/games/mechanics`.
- `GET /api/v1/recommendations/similar/{bgg_id}?method=content|collaborative|hybrid`,
  `/recommendations/for-me`, `/recommendations/context`, `/recommendations/semantic`, `POST /index`.
- `POST /api/v1/chat` — keyword-extraction advisor over Mongo, no LLM memory between turns.

Recommenders live in `app/recommenders/`: `content_based.py` (one-hot categories + mechanics +
weight/players/playtime, cosine), `collaborative.py` (item-item cosine over `user_actions`,
built in memory at first call), `hybrid.py`, `embedding.py` (Qdrant).

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
