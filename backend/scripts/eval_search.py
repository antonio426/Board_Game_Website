"""Score search and filter quality against tests/golden_queries.json.

Run it before and after any change to ranking, filtering or the quality gate.
A change that improves one query usually costs another; without a fixed set you
cannot tell which way the trade went.

Usage:
    cd backend && .venv/bin/python scripts/eval_search.py
    cd backend && .venv/bin/python scripts/eval_search.py --base http://localhost:8010/api/v1
    cd backend && .venv/bin/python scripts/eval_search.py --save tests/eval_baseline.json
    cd backend && .venv/bin/python scripts/eval_search.py --compare tests/eval_baseline.json
"""
import argparse
import json
import sys
import urllib.parse
import urllib.request
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
GOLDEN = BACKEND / "tests" / "golden_queries.json"

ZH_MIN_RATING = 6.0
ZH_MIN_USERS_RATED = 50

# Mirrors LANGUAGE_DEPENDENCE_BANDS in app/core/filters.py.
LANGUAGE_BANDS = {
    "low": {
        "No necessary in-game text",
        "Some necessary text - easily memorized or small crib sheet",
    },
    "medium": {"Moderate in-game text - needs crib sheet or paste ups"},
    "high": {
        "Extensive use of text - massive conversion needed to be playable",
        "Unplayable in another language",
    },
}


def fetch(base: str, endpoint: str, params: dict) -> list[dict]:
    path = "/games/search" if endpoint == "search" else "/games"
    query = urllib.parse.urlencode({k: str(v).lower() if isinstance(v, bool) else v for k, v in params.items()})
    with urllib.request.urlopen(f"{base}{path}?{query}", timeout=30) as response:
        return json.load(response).get("games", [])


# List responses carry what a card renders; the description and the subdomain
# ranks live only on the detail document. Two conditions are stated in terms of
# those fields, so the games they judge are looked up once each.
DETAIL_FIELDS = {"has_description": "description_en", "family": "subcategory_ranks"}
_detail_cache: dict[int, dict] = {}


def fetch_detail(base: str, bgg_id: int) -> dict:
    if bgg_id not in _detail_cache:
        with urllib.request.urlopen(f"{base}/games/{bgg_id}", timeout=30) as response:
            _detail_cache[bgg_id] = json.load(response)
    return _detail_cache[bgg_id]


def with_detail(base: str, games: list[dict], conditions: dict) -> list[dict]:
    """Merge in the detail-only fields the stated conditions actually read."""
    wanted = [field for key, field in DETAIL_FIELDS.items() if conditions.get(key)]
    if not wanted:
        return games
    merged = []
    for game in games:
        detail = fetch_detail(base, game["bgg_id"])
        merged.append({**game, **{field: detail.get(field) for field in wanted}})
    return merged


def tag_names(game: dict, field: str) -> set[str]:
    return {
        (item.get("name") or "") if isinstance(item, dict) else str(item)
        for item in game.get(field) or []
    }


def satisfies(game: dict, conditions: dict) -> bool:
    """Whether one result honours every stated condition."""
    if conditions.get("has_description") and not (game.get("description_en") or "").strip():
        return False

    players = conditions.get("players_include")
    if players is not None:
        if (game.get("min_players") or 0) > players or (game.get("max_players") or 0) < players:
            return False

    playtime = conditions.get("max_playtime_at_most")
    if playtime is not None:
        longest = game.get("max_playtime") or game.get("min_playtime") or 0
        if longest <= 0 or longest > playtime:
            return False

    rating = conditions.get("bgg_rating_at_least")
    if rating is not None and (game.get("bgg_rating") or 0) < rating:
        return False

    users_rated = conditions.get("users_rated_at_least")
    if users_rated is not None and (game.get("users_rated") or 0) < users_rated:
        return False

    wanted_categories = conditions.get("category_any")
    if wanted_categories and not (tag_names(game, "categories") & set(wanted_categories)):
        return False

    wanted_mechanics = conditions.get("mechanic_any")
    if wanted_mechanics and not (tag_names(game, "mechanics") & set(wanted_mechanics)):
        return False

    family = conditions.get("family")
    if family:
        subdomains = {
            entry.get("subdomain")
            for entry in game.get("subcategory_ranks") or []
            if isinstance(entry, dict)
        }
        if family not in subdomains:
            return False

    band = conditions.get("language_band")
    if band and game.get("language_dependence") not in LANGUAGE_BANDS[band]:
        return False

    age = conditions.get("min_age_at_most")
    if age is not None:
        game_age = game.get("min_age") or 0
        if game_age <= 0 or game_age > age:
            return False

    year = conditions.get("year_at_least")
    if year is not None and (game.get("year_published") or 0) < year:
        return False

    designers = conditions.get("designer_any")
    if designers:
        names = {name for name in game.get("designers") or [] if isinstance(name, str)}
        if not names & set(designers):
            return False

    if conditions.get("zh_gate"):
        if (game.get("bgg_rating") or 0) < ZH_MIN_RATING and (game.get("users_rated") or 0) < ZH_MIN_USERS_RATED:
            return False

    return True


def run_case(base: str, case: dict, top_k: int) -> dict:
    games = fetch(base, case.get("endpoint", "search"), case.get("params", {}))[:top_k]
    ids = [game.get("bgg_id") for game in games]

    result = {"id": case["id"], "returned": len(games), "top_ids": ids[:3]}

    expected = case.get("expect_ids")
    if expected:
        found = [gid for gid in expected if gid in ids]
        result["recall"] = len(found) / len(expected)

    expected_top = case.get("expect_top_id")
    if expected_top is not None:
        result["top1"] = 1.0 if ids[:1] == [expected_top] else 0.0

    conditions = case.get("conditions")
    if conditions:
        if games:
            judged = with_detail(base, games, conditions)
            result["precision"] = sum(satisfies(g, conditions) for g in judged) / len(judged)
        else:
            result["precision"] = 0.0

    if not games:
        result["zero_results"] = True

    return result


def mean(values: list[float]) -> float | None:
    return sum(values) / len(values) if values else None


def summarise(results: list[dict]) -> dict:
    return {
        "cases": len(results),
        "recall": mean([r["recall"] for r in results if "recall" in r]),
        "top1": mean([r["top1"] for r in results if "top1" in r]),
        "precision": mean([r["precision"] for r in results if "precision" in r]),
        "zero_results": sum(1 for r in results if r.get("zero_results")),
    }


def fmt(value: float | None) -> str:
    return "  n/a" if value is None else f"{value:5.1%}"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--base", default="http://localhost:8000/api/v1")
    parser.add_argument("--save", help="write the run to this JSON file")
    parser.add_argument("--compare", help="diff the run against a saved JSON file")
    parser.add_argument("--verbose", action="store_true", help="print every case, not just failures")
    args = parser.parse_args()

    golden = json.loads(GOLDEN.read_text())
    top_k = golden.get("top_k", 10)

    results = []
    for case in golden["cases"]:
        try:
            results.append(run_case(args.base, case, top_k))
        except Exception as exc:
            results.append({"id": case["id"], "error": str(exc), "zero_results": True})

    for result in results:
        failed = (
            result.get("error")
            or result.get("zero_results")
            or result.get("recall", 1.0) < 1.0
            or result.get("top1", 1.0) < 1.0
            or result.get("precision", 1.0) < 1.0
        )
        if failed or args.verbose:
            marks = [f"{k}={fmt(result[k])}" for k in ("recall", "top1", "precision") if k in result]
            note = result.get("error") or ("ZERO RESULTS" if result.get("zero_results") else "")
            print(f"{'FAIL' if failed else 'ok  '} {result['id']:<34} {' '.join(marks):<40} {note}")

    summary = summarise(results)
    print(
        f"\ncases={summary['cases']}  recall@{top_k}={fmt(summary['recall'])}"
        f"  top1={fmt(summary['top1'])}  precision@{top_k}={fmt(summary['precision'])}"
        f"  zero-result cases={summary['zero_results']}"
    )

    if args.compare:
        previous = json.loads(Path(args.compare).read_text())
        print(f"\nvs {args.compare}:")
        for metric in ("recall", "top1", "precision"):
            before, after = previous["summary"].get(metric), summary.get(metric)
            if before is None or after is None:
                continue
            print(f"  {metric:<10} {before:5.1%} -> {after:5.1%}  ({after - before:+.1%})")

    if args.save:
        path = Path(args.save)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"summary": summary, "results": results}, indent=2, ensure_ascii=False))
        print(f"\nsaved {path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
