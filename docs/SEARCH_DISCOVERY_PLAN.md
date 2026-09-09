# 搜尋 / 篩選 / 推薦 品質計畫

> 目標：使用者用任何方式（打字、選標籤、問卷、聊天）都能在 3 步內找到「真的會買、會玩」的桌遊。
> 對象讀者：接手實作的人。每個項目都寫到可以直接動工的程度。
> 與 `UX_ROADMAP.md` 的分工：那份談頁面體驗，這份談檢索與排序的正確性與品質。

---

## 0. 現況體檢（實測數字）

| 觀察 | 數字 | 影響 |
|---|---|---|
| `board_games` 總量 | 180,401 | — |
| 有 `description_en` 的（等同「真遊戲」） | 43,401 | 所有 endpoint 都用它當品質閘門 |
| `users_rated >= 1000` | 5,155 | 真正值得推薦的核心集合 |
| `bgg_weight > 0` | **9** | 複雜度篩選與 content-based 的 weight 維度形同虛設 |
| `name_zh` 非空 | 3,280 | zh 介面大多數遊戲仍顯示英文 |
| `description_zh` 非空 | **14** | 中文描述基本上不存在 |
| Qdrant 向量 | 7,833 | 語意搜尋只覆蓋約 18% 的品質遊戲 |
| `board_games` 索引 | 只有 `_id` | 每次列表 / 搜尋 / count 都是 180k 全表掃描 |
| `user_actions` / `users` | 15 / 0 | 協同過濾實際上永遠回空陣列 |

### 三個明確的 bug

1. **`num_ratings` 這個欄位不存在。** `backend/app/api/v1/games.py` 有三處在查它：
   `_should_hide_low_rated()`、`list_games()` 的 zh locale `$or` 閘門、`search_games()` 的
   `min_ratings` 參數。實際欄位名是 `users_rated`。目前這些條件全部不會命中，
   `min_ratings` 傳任何值都等於沒傳。
2. **`min_weight` / `max_weight` 篩選會回幾乎空的結果**，因為 `bgg_weight` 只有 9 筆 > 0。
   前端 `/games` 頁面卻把它當成主要篩選欄位之一。
3. **`bgg_rank` 全部 180k 筆都有值**，其中 155,388 筆 rank > 25,000。`sort=rank`（預設）在
   列表尾端等於隨機排序。

---

## 1. Phase 0 — 修正與地基（約 1 天）✅ **DONE**（見第 10 節執行紀錄）

沒有這一段，後面任何篩選功能都是蓋在流沙上。

### P0.1 修 `num_ratings` → `users_rated`（30 分鐘） ✅
- 檔案：`backend/app/api/v1/games.py`
- 三處全部改名，並把 zh locale 的品質閘門改成有意義的條件：
  `bgg_rating >= 6 OR users_rated >= 50`。
- 驗證：`GET /api/v1/games/search?min_ratings=1000` 必須回非空且 total 合理（約 5,155 的子集）。

### P0.2 建立 Mongo 索引（1 小時） ✅
新增 `backend/scripts/ensure_indexes.py`，並在 FastAPI startup 呼叫一次（idempotent）：

```python
INDEXES = [
    ([("bgg_id", 1)], {"unique": True}),
    ([("bgg_rank", 1)], {}),
    ([("bgg_rating", -1)], {}),
    ([("users_rated", -1)], {}),
    ([("year_published", -1)], {}),
    ([("categories.name", 1)], {}),
    ([("mechanics.name", 1)], {}),
    ([("min_players", 1), ("max_players", 1)], {}),
    ([("quality_score", -1)], {}),          # 見 P2.1
    ([("name_en", "text"), ("name_zh", "text"), ("aliases", "text")], {"name": "name_text"}),
]
```
- 驗收：`explain()` 對 `/games?sort=rank&page=1` 顯示 `IXSCAN` 而非 `COLLSCAN`；
  p95 回應時間 < 150 ms（現況先量一次當 baseline）。

### P0.3 抽出單一品質閘門（1 小時） ✅
- 新增 `backend/app/core/quality.py`：

```python
QUALITY_FILTER = {"description_en": {"$exists": True, "$ne": ""}}

def quality_gate(locale: str = "en", min_users_rated: int = 0) -> dict: ...
```
- `games.py`、`recommendations.py`、`chat.py` 三處各自複製的
  `{"description_en": {"$exists": True, "$ne": ""}}` 全部改呼叫它。
- 理由：目前品質定義散在 6 個地方，之後要調整（例如改成 `users_rated >= 30`）會漏改。

### P0.4 補一次資料健檢腳本（1 小時） ✅
- 新增 `backend/scripts/data_health.py`：印出本文件第 0 節那張表。
- 每次 crawler / enricher 跑完後執行，避免覆蓋率默默退化。

---

## 2. Phase 1 — 資料補齊（約 2 天） — 進行中（見第 10 節）

篩選品質的天花板是資料覆蓋率，不是 UI。

### P1.1 回填 `bgg_weight`（4–6 小時）
- 來源：BGG XML API2 `/thing?id=...&stats=1` → `<averageweight>`。
- 範圍：先做 43,401 筆有 `description_en` 的；批次 20 個 id / request，
  BGG 建議間隔 ~2 秒，約 45 分鐘可跑完一輪。
- 寫入：`bgg_weight`（float）+ `bgg_weight_votes`（int，投票數少於 5 的視為不可信，寫 0）。
- 沿用既有寫法：參考 `backend/app/crawlers/bgg_crawler.py` 的 request/parse 模式，
  新增 `backend/scripts/backfill_weight.py`。
- 驗收：`bgg_weight > 0` 從 9 筆變成 > 35,000 筆；`/games?min_weight=2&max_weight=3` 回合理結果。

### P1.2 語意搜尋：換掉假的 embedding，再談覆蓋率（1–1.5 天，**範圍已擴大**）

> Phase 0 執行時發現：`app/recommenders/embedding.py::_text_to_vector` 是把文字做 SHA-256
> 再經 `sin()` 攤成 384 維，**完全不是 embedding**。同義的兩段文字會得到毫不相關的向量，
> 所以 Qdrant 回來的東西是雜訊（實測搜 "deck building card game" 回傳
> "Vanished Planet: Racial Advantage Expansion"）。原本規劃的「把 7.8k 索引補到 43k」
> 只會讓雜訊變多，必須先換掉向量產生方式。
>
> 現況已用 `SEMANTIC_SEARCH_ENABLED`（預設 `false`）把語意路徑關掉，改走字詞搜尋，
> 避免使用者拿到亂數結果。換完模型後把它打開。

- 選型：`fastembed`（`BAAI/bge-small-en-v1.5`，384 維，剛好對上既有 `VECTOR_SIZE`，
  ONNX CPU 可跑，不需要 GPU）。中文查詢要一起支援的話用 `BAAI/bge-m3` 或
  `paraphrase-multilingual-MiniLM-L12-v2`（維度不同，需改 `VECTOR_SIZE` 並重建 collection）。
- 43k 筆 × bge-small CPU 約 20–40 分鐘可編碼完成。
- `app/recommenders/embedding.py::index_games` 的批次邏輯可留，改成可續跑
  （記錄已索引的 `bgg_id`，跳過已存在的 point）。
- 改成可續跑（記錄已索引的 `bgg_id`，跳過已存在的 point），跑滿整個品質集合。
- Embedding 文本建議組成：`name_en + name_zh + categories + mechanics + description_en 前 500 字`。
- 索引完成後在 Qdrant 開啟 payload index（`categories`、`mechanics`、`users_rated`），
  讓語意搜尋可以帶條件過濾，而不是先取 200 筆再回 Mongo 二次篩（目前 `search_games` 的做法會漏結果）。
- 驗收：`points_count >= 43,000`，`SEMANTIC_SEARCH_ENABLED=true`；`/games/search?q=deck building space&semantic=true` 首 10 筆
  人工看有 8 筆以上合理。

### P1.3 中文覆蓋率（1 天，可與 P1.1 平行）
- `name_zh` 3,280 → 目標覆蓋 `users_rated >= 500` 的全部（約 8–9k 款）。
- 來源優先序：既有 `zhuoyouku_enricher` / `wikidata_enricher` → 翻譯 API fallback。
- `description_zh` 只有 14 筆，先不強求全量；優先做 `users_rated >= 1000` 的 5,155 款。
- 每筆新譯名同時 append 進 `aliases`，維持既有 CJK 搜尋policy。

---

## 3. Phase 2 — 排序品質（約 2 天） ✅ DONE

### P2.1 統一 `quality_score`（4 小時）
現在排序依 `bgg_rating` 或 `bgg_rank`，兩者都有洞：`bgg_rating` 只有 43k 筆、
`bgg_rank` 尾端無意義、`bgg_avg_rating`（140k 筆）沒有投票數加權。

用 Bayesian 平均，離線算一次寫進欄位：

```
quality_score = (v / (v + m)) * R + (m / (v + m)) * C
  v = users_rated
  R = bgg_avg_rating
  C = 全站平均分（約 6.4，跑一次 aggregate 取得）
  m = 100（先驗投票數門檻）
```
- 新增 `backend/scripts/compute_quality_score.py`，crawler 跑完後執行。
- `SORT_MAP` 新增 `"quality": [("quality_score", -1)]`，並把**預設 sort 從 `rank` 改成 `quality`**。
- 驗收：預設列表首頁不再出現 `users_rated = 0` 的冷門遊戲。

### P2.2 文字搜尋相關性（4–5 小時）
現在 `q` 是純 `$regex` OR，沒有相關性分數，`sort` 一律 `bgg_rating`，所以搜 "catan"
可能先回傳一堆擴充。改成分層：

1. 完全相符（`name_en` / `name_zh` / `aliases` 精確）→ score 100
2. 前綴相符 → score 50
3. 子字串相符 → score 20
4. text index 相符（P0.2 已建）→ score 10
最終排序 `score DESC, quality_score DESC`，並在 response 加 `match_type` 欄位。
- 實作位置：`games.py` 抽出 `app/core/search.py::build_name_query(q)`，
  讓 `list_games`、`search_games`、`chat.py::_search_games` 共用同一份邏輯（目前三份幾乎重複的 regex 組裝）。
- 對應 `UX_ROADMAP` 的 **A5**（搜尋結果沒有相關性依據）。

### P2.3 擴充與本體分離（2 小時）
- `is_expansion` 目前只有 1 筆為 true，實際上 BGG 有大量擴充混在列表裡。
- 用 `expansions` / BGG `type=boardgameexpansion` 回填 `is_expansion`。
- 列表預設 `is_expansion: {$ne: true}`，加一個 "Include expansions" 開關。
- 驗收：搜 "Catan" 首頁不再被 20 個擴充佔滿。

---

## 4. Phase 3 — 篩選體驗（約 2–3 天） ✅ DONE

前提：Phase 0/1 完成，否則做出來的控制項篩不到東西。

### P3.1 多選 + AND/OR + 排除（5–6 小時）
- 後端 `search_games` 已支援逗號分隔 `$in`（OR）。新增：
  - `categories_mode=any|all`（`$in` vs `$all`）
  - `exclude_categories` / `exclude_mechanics`（`$nin`）
- 前端把 `/games` 與 `/explore` 的 `<select>` 換成 chip 多選，
  chip 三態：未選 / 包含（綠）/ 排除（紅刪除線）。
- 對應 `UX_ROADMAP` **C1 + C2**。

### P3.2 Facet 數量（4 小時）
- 新增 `GET /api/v1/games/facets`：吃跟列表相同的 filter 參數，
  回傳每個 category / mechanic / 人數區間 / 時長區間在**目前條件下**還剩幾筆。
- 實作用單一 `$facet` aggregation，Redis 快取 120 s。
- UI：chip 後面顯示 `(123)`，數量為 0 的 chip 淡出但不隱藏（避免版面跳動）。
- 效益：使用者不會選到一組必然 0 筆的組合，這是「好篩選」跟「一堆下拉選單」的分水嶺。

### P3.3 篩選狀態進 URL（3 小時）
- `/games` 目前狀態只存在 `useState`，重整就掉、也無法分享。
- 改用 `useSearchParams` + `router.replace`，所有 filter 皆可 deep link。
- 順帶解決 `UX_ROADMAP` **C5**（filter preset / share link）與瀏覽器上一頁行為。

### P3.4 有意義的區間控制項（3 小時）
- 人數：改成「我要 N 人玩」單一輸入，後端轉成 `min_players <= N <= max_players`
  （現在前端傳 `min_players` 但語意是 `$lte`，容易誤解）。
- 時長：預設 bucket（< 30 / 30–60 / 60–120 / > 120 分鐘）。
- 複雜度：P1.1 回填後才開放，用 1–5 slider + 文字標籤（輕鬆 / 中等 / 重度）。

---

## 5. Phase 4 — 推薦品質（約 3 天） ✅ DONE

### P4.1 推薦理由（4–5 小時）
- `/recommendations/similar/{id}` 回傳加上
  `reasoning: {matched_categories: [...], matched_mechanics: [...], score_breakdown: {...}}`。
- content-based 已經算出 one-hot 交集，只是丟掉了；保留下來即可，成本很低。
- UI 顯示「因為你在看的這款也有：工人放置、經濟」。
- 對應 `UX_ROADMAP` **F2 / B5**。

### P4.2 冷啟動路徑（1 天）
- 現況：協同過濾沒有資料（15 actions / 0 users），`hybrid` 實際只有 content-based 在作用。
- 明確定義降級鏈：
  `個人化 CF（需 >= 5 個 action）→ content-based（需至少 1 個收藏或當前遊戲）→ 問卷向量 → quality_score 熱門榜`
- `/survey` 的答案要存成 user preference vector（`liked_categories`、`liked_mechanics`、
  `preferred_weight`、`preferred_players`），餵進既有的
  `ContentBasedRecommender.recommend_for_preferences()`（已寫好但沒人呼叫）。

### P4.3 結果多樣性（3 小時）
- content-based 的 cosine 會回傳一整排同系列 / 同出版社的遊戲。
- 套 MMR（λ ≈ 0.7）：`score = λ * relevance - (1-λ) * max_similarity_to_already_selected`。
- 另加硬規則：同一 `series` 最多 2 款、同一設計師最多 2 款。

### P4.4 Chat 記憶與工具化（1 天）
- `chat.py` 目前每輪都重新關鍵字搜尋，不記得上一輪（`UX_ROADMAP` **F4**）。
- 存 session 對話進 Redis（key `chat:{session_id}`，TTL 30 分鐘），
  把已擷取的條件（人數 / 時長 / 類型）累積成 filter state，讓「那再少一點人的呢」可以運作。

---

## 6. Phase 5 — 量測（0.5 天，但要先做） ✅ DONE

沒有這段就無法判斷上面任何一項有沒有改善。

- 建 `backend/tests/golden_queries.yaml`：30 條查詢 + 期望結果（例如
  `"deck building"` 前 10 應包含 Dominion；`"2人 30分鐘 輕鬆"` 前 10 應全部符合條件）。
- `backend/scripts/eval_search.py` 算 precision@10 與條件符合率，每次改排序前後各跑一次。
- 前端加最小 analytics 事件：`search_submitted`、`filter_applied`、`result_clicked`、
  `zero_results`。zero-result 查詢每週看一次，是最便宜的品質訊號來源。

---

## 7. 建議執行順序

| 週次 | 內容 | 產出 |
|---|---|---|
| 1（前半） | Phase 0 全部 + Phase 5 的 golden queries | 索引就位、bug 修掉、有 baseline 數字 |
| 1（後半） | P1.1 weight 回填 + P1.2 Qdrant 補齊 | 複雜度篩選可用、語意搜尋覆蓋 100% |
| 2（前半） | P2.1 quality_score + P2.2 相關性 + P2.3 擴充分離 | 排序不再靠壞掉的 rank |
| 2（後半） | P3.1 多選 + P3.2 facet counts | 篩選變成真的能收斂結果 |
| 3 | P3.3 URL 狀態 + P3.4 區間控制 + P4.1 推薦理由 | 可分享、可理解 |
| 4 | P4.2 冷啟動 + P4.3 多樣性 + P4.4 chat 記憶 | 推薦系統站得住 |
| 平行 | P1.3 中文覆蓋率 | zh 介面不再半英文 |

## 8. 每個 Phase 的驗收條件

- Phase 0：`explain()` 無 `COLLSCAN`；`min_ratings` 參數有效；p95 < 150 ms。
- Phase 1：`bgg_weight > 0` > 35k；Qdrant `points_count` >= 43k。
- Phase 2：golden queries precision@10 相對 baseline 提升；預設列表無 `users_rated = 0`。
- Phase 3：任意 filter 組合都能從 URL 還原；facet 數字與實際 total 一致。
- Phase 4：每個推薦都帶得出理由；未登入且無收藏時仍有合理結果。

## 9. 需要你決定的

1. **BGG 抓取速率**：P1.1 / P2.3 都要重跑 BGG API。要一次跑滿 43k，還是只補
   `users_rated >= 100` 的 23k？後者快 1/2 但複雜度篩選會有洞。
2. **中文翻譯來源**：P1.3 要不要接付費翻譯 API（品質好但有成本），
   還是只用既有 enricher 能抓到的？
3. **預設排序改成 `quality`** 會改變首頁與列表的既有觀感，確認可以動嗎？
4. **擴充預設隱藏**（P2.3）符合你的產品定位嗎？有些使用者是專門找擴充的。


---

## 10. 執行紀錄

### Phase 0（已完成）

| 項目 | 動作 |
|---|---|
| P0.1 | `num_ratings` → `users_rated`（3 處）。zh locale 閘門改成 `bgg_rating >= 6 OR users_rated >= 50` |
| P0.2 | `app/core/indexes.py` + `scripts/ensure_indexes.py`，10 個索引已建（2.9 秒），FastAPI lifespan 開機時 idempotent 重跑 |
| P0.3 | `app/core/quality.py`（`QUALITY_FILTER` / `quality_gate()` / `is_low_quality()` / `merge_filters()`），`games.py`、`recommendations.py`、`chat.py` 全部改用 |
| P0.4 | `scripts/data_health.py`，印出覆蓋率表並對已知空欄位示警 |
| 追加 | `app/core/tags.py`：分類/機制名稱正規化，讓篩選走索引而非 case-insensitive regex |
| 追加 | `/games/categories`、`/games/mechanics` 排除 `name` 為 null 的標籤（原本清單第一名是 `null`） |
| 追加 | `/games/random` 改成從品質集合 `$match` + `$sample`，不再抽到沒有描述的 stub，也移除了原本的無上限遞迴 |
| Phase 5 | `tests/golden_queries.json`（33 條）+ `scripts/eval_search.py` + `tests/eval_baseline.json` |

### 修正前後對照（實測）

| 項目 | 修正前 | 修正後 |
|---|---|---|
| `min_ratings=1000` 搜尋結果 | 0 筆（欄位不存在） | 4,410 筆 |
| `/games` 分類篩選（真實標籤名） | 231 ms | 18 ms |
| `/games` 機制篩選 | ~240 ms | 14 ms |
| `/games?sort=rank` 列表 | 99 ms | 95 ms |
| Mongo 查詢計畫 | `COLLSCAN` | `IXSCAN`（671 docs examined） |
| `/games/random` | 可能回無描述的 stub | 一律有描述 |
| zh locale 可見遊戲 | 依賴壞掉的條件 | 25,466 筆 |

### Golden query baseline（`tests/eval_baseline.json`）

```
cases=33  recall@10=84.2%  top1=66.7%  precision@10=84.3%  zero-result cases=4
```

未通過的 10 條，正好對應後面 Phase 要處理的事：

- **top1 失敗**（catan / dominion / ticket to ride）：搜尋沒有相關性排序，本體被同名擴充壓過 → **P2.2 + P2.3**
- **`filter-short-games` precision 0%**：`max_playtime=30` 在後端的語意是
  `max_playtime >= 30`（「遊戲時長上限至少 30 分」），不是使用者以為的「30 分鐘內玩得完」。
  人數篩選同樣只套了單邊（precision 90%）→ **P3.4 必須修語意，這是目前最容易誤導使用者的篩選器**
- **4 條 semantic 案例 zero results**：多字概念查詢（"cooperative game about curing diseases"）
  用整句 regex 比對名稱必然 0 筆 → **P1.2（真 embedding）+ P2.2**

### 其他發現（尚未處理）

- 部分遊戲的 `categories` / `mechanics` 陣列裡有 `name` 為 null 的元素（例如 Splendor
  的分類是 `,,`）。清單端點已過濾，但資料本身要在下次 enrich 時補。
- `name_zh` 有不少其實是日文（Catan = カタン、Pandemic = パンデミック、
  Ticket to Ride = 乗車券）。P1.3 補中文時要一併判斷語言，不能只看「有沒有值」。
- `bgg_rank` 前段就有並列（rank 2 同時是 Ark Nova 與 Kingdom Death: Monster，
  後者 `users_rated = 0`），再次佐證 P2.1 需要用 `quality_score` 取代 rank 當預設排序。


### Phase 1-4（本次執行）

| 項目 | 動作 | 狀態 |
|---|---|---|
| P1.1 | BGG XML API 已改為需認證（401）。改用 `api.geekdo.com/api/dynamicinfo`，一次拿到 weight、最佳人數投票、語言需求、subdomain 排名 | 背景跑，resumable |
| P1.2 | `_text_to_vector` 的 SHA-256 假向量換成 fastembed。先試多語 paraphrase 模型，檢索品質差；改用 `BAAI/bge-small-en-v1.5`（384 維，不用改 collection） | 重建索引中 |
| P1.3 | 中文覆蓋率：`scripts/clean_zh_names.py` 把 641 筆日文名稱移進 `aliases` 並清空 `name_zh`（カタン、乗車券 等），zh 介面改回退到英文而不是顯示日文；15 筆從 alias 提升為真正的中文名。翻譯補齊仍待決定 | 部分完成 |
| P2.1 | `quality_score` Bayesian（m=1000），預設排序改成 `quality` | ✅ |
| P2.2 | `app/core/search.py`：完全相符 100 > 前綴 60 > 詞邊界 40 > 子字串 20，擴充 -25，加 `quality_score` 當 tie-break | ✅ |
| P2.3 | `is_expansion`：不需要任何 API。匯入時就存了 `bgg_rank = 99999` 代表未上榜，而 BGG 只要有約 30 個評分就會給基本款排名、擴充永遠不排名。用「未上榜 且 `users_rated >= 30`」判定，對 3,296 筆有權威 subtype 的資料驗證：43 個擴充全中、3,253 個基本款全對，零誤判。一次跑完標出 12,251 筆 | ✅ |
| P3.1 | 多選 + AND/OR (`categories_mode`) + 排除 (`exclude_categories`) | ✅ |
| P3.2 | `GET /games/facets`：單一 `$facet` 回傳每個選項在目前條件下的剩餘數量（276 ms） | ✅ |
| P3.3 | `/games` 篩選狀態全部進 URL，可分享可重整 | ✅ |
| P3.4 | 新增語意明確的 `players` / `playtime_max` / `playtime_min`；舊參數保留但文件標明是 range-overlap | ✅ |
| P4.1 | `/recommendations/similar` 每筆帶 `reasoning.matched_categories` / `matched_mechanics`，前端顯示「共同點」 | ✅ |
| P4.2 | 降級鏈：協同（需 5+ 互動）→ content → 問卷 taste profile → `quality_score` 熱門榜。新增 `POST /recommendations/preferences`，問卷改用真實標籤名 | ✅ |
| P4.3 | `diversity.py` MMR（λ 0.7）+ 同系列/同設計師各上限 2 | ✅ |
| P4.4 | Chat 用 Redis 存 session intent（30 分鐘），「再短一點的呢」會沿用上一輪的人數 | ✅ |

### 順手修掉的 bug

- `/games/search?semantic=true` 呼叫 `search_similar()` 沒 await 且用錯 kwarg → 永遠拋例外走 regex fallback。
- `/explore` 的語意搜尋打 `/games/semantic`，**這個 endpoint 從來不存在** → 語意模式一直是空結果。
- `ContentBasedRecommender` 對全部 180k 筆（含 137k stub）建 285 維 dense 向量後逐一比對；改成只載入可推薦的語料 + 稀疏標籤集合。
- 「重/複雜」在 chat 裡設成 `max_weight = 5.0`，等於沒有篩選；改成設下限 3.5。
- `$facet` 的 key 不能含 `.`，weight bucket key（`weight_1.0_2.0`）會讓 endpoint 回 500。

### Golden query 結果

題目從 33 條加到 37 條（多測多選 AND 模式、排除篩選、最佳人數、語意檢索）。

| | Phase 0 baseline | Phase 1-4 |
|---|---|---|
| recall@10 | 84.2% | **100%** |
| top1 | 66.7% | **100%** |
| precision@10 | 84.3% | **100%** |
| zero-result cases | 4 | **0** |

37 條全過。語意類案例是在向量索引只建到 6,400 筆（依 `users_rated` 由高到低）時測的，
熱門遊戲已經覆蓋；索引繼續補會影響冷門查詢，不影響這組結果。

### 未完成 / 待決定

1. **P1.3 中文覆蓋率沒做**：`name_zh` 仍只有 3,280 筆，且其中不少是日文（カタン、乗車券）；`description_zh` 只有 14 筆。要不要接付費翻譯 API 仍待你決定。
2. **背景任務尚未跑完**：
   - `scripts/backfill_dynamicinfo.py`：目前 `bgg_weight` 覆蓋 9,423 筆（原本 9 筆）。geekdo 超過每秒約 10 次請求會回 429，所以併發壓到 2，剩下約 34k 筆需要數小時。可續跑，中斷後重跑會自動跳過已完成的。
   - `scripts/index_embeddings.py --recreate`：向量重建中，依 `users_rated` 由高到低，所以熱門遊戲先進索引；語意搜尋的品質隨覆蓋率提升。機器負載高時約每分鐘 700 筆。
3. **`backfill_subtypes.py` 只跑了 3,296 筆**：其餘由 `mark_expansions.py` 用排名判定（對這 3,296 筆驗證是零誤判）。真的要 100% 權威標記再補跑，但目前沒有必要。
4. **語意搜尋僅英文**：中文查詢走字詞比對。要中文語意檢索需換多語 retrieval 模型並重建 collection（維度會變）。


---

## 11. 標籤中文化與篩選強化（第二輪）

### 修掉的

| 問題 | 影響 | 修法 |
|---|---|---|
| `bgg_categories`(85) / `bgg_mechanics`(196) 兩張完整中文對照表從沒被讀取 | 24 個標籤顯示英文（含最常見的 Hand Management） | 新增 `app/core/vocab.py` 當唯一權威，端點改 join 記憶體詞彙表 |
| `/games/mechanics` 的 `$limit: 100` | 196 個機制有 96 個使用者永遠看不到 | 移除；改為左接完整詞彙表，未使用的標籤以 count 0 出現 |
| 10,959 筆標籤是舊字串陣列 | 標籤篩選漏掉 25% 的遊戲、詳情頁 chip 空白 | `scripts/backfill_tag_objects.py` 一次修好；`_format_game` 另外做讀取時防呆 |
| 六處連結送 `?category=`，games 頁讀 `cat=` | 標籤頁與詳情頁的標籤連結 100% 失效 | 產生端改用短鍵，`fromSearchParams` 相容舊參數 |
| `paged_search` 有 `q` 時強制相關性重排 | 使用者選的排序被無聲忽略 | 加 `relevance_rank`，只有排序維持預設時才重排 |
| `designers`/`publishers` 查 `designers.name` | 永遠 0 筆（實際是字串陣列） | 改查陣列本身，Reiner Knizia 從 0 變 475 筆 |
| facet 分桶與篩選條件各走各的 | ≤240 分鐘沒數字、複雜度 3-4 那桶被吃掉 | facet stage 改由 `build_filters` 產生，結構上保證數字一致 |
| 複雜度 `$lte 2.0` 把未評分的 0 當成輕鬆 | 約 7k 筆未評分遊戲被算進「輕鬆」 | 加 `$gt: 0` 下限，light 從 29,370 修正為 22,604 |
| `POST /translate/terms` 的 `translated or cname` | 未驗證的公開寫入端點，把英文寫進 `name_zh` | 連同兩份重複字典一起刪除 |
| `geekdo_enricher` 把標籤寫成字串陣列 | 每跑一次就讓文件退化 | 改寫物件；查不到翻譯給 `None` 並寫 log |

### 新增的

- **中文可以拿來篩選**：`build_filters_async` 把中文標籤名對回英文，`categories=卡牌遊戲` 與 `categories=Card Game` 同樣回 11,815 筆。不用 `name_zh` regex——那會放棄索引。
- **標籤搜尋框**：中英文同時比對（「工人」與 "worker" 都找得到工人放置），已選標籤釘在最前面。
- **五個新篩選**（都是帶數量的 chip，沒有滑桿）：
  - 遊戲類型（BGG 大類）：戰棋 4,612 / 家庭 3,665 / 策略 3,286 / 主題 1,832 / 抽象 1,506 / 兒童 1,147 / 派對 997 / 卡牌對戰 383
  - 文字量：幾乎無文字 13,981 / 少量 6,341 / 大量 4,076
  - 適合年齡：6+ 4,445 / 8+ 14,560 / 10+ 22,530 / 12+ 30,650
  - 出版年份：近五年 7,630 / 2016 年後 15,178 / 2005 年前 17,366
  - 熱門程度：較多人玩過 17,530 / 熱門 4,347
- **快速開始 preset**：兩人一小時 10,031 筆 / 派對開場 551 筆 / 親子同樂 2,744 筆（都遠高於「低於 100 筆就砍掉」的門檻）
- **`sort=popular`**：依評分人數排序，對沒有 BGG 背景的人最好懂
- **概念搜尋開關併進 `/games`**：`/explore` 改成 307 導向，不再維護第二套參數語意相反的篩選 UI

### 驗證

每個 chip 上的數字都等於點下去的結果數（實測 playtime 四段、weight 三段、family 八段、language 三段、age 四段、year 三段、popularity 兩段全部相符）。facet 端點 9 個並行 aggregation，334 ms、快取 120 秒。`subcategory_ranks.subdomain` 索引 `docsExamined == nReturned == 997`。

Golden set 從 37 題擴到 **47 題**（新增中文標籤輸入、四個新篩選、designer、popular 排序、preset），全部通過：recall@10 / top1 / precision@10 都是 100%。

---

## 12. Phase 6 — 中文可讀、回應變輕（第三輪）

### 起點：背景任務跑完後的實測

Phase 1 掛在背景的兩件事都完成了，驗收條件達標：

| 指標 | Phase 1 當下 | 現在 |
|---|---|---|
| `bgg_weight > 0` | 9,423 | **36,632**（可展示遊戲的 84.4%） |
| Qdrant 向量 | 6,400 | **43,401**（等於整個可展示集合） |
| `dynamicinfo_at` | — | 43,390 |
| golden queries | 47 題全過 | 47 題仍全過（向量補滿沒有造成回歸） |

補滿之後才看得到的三個問題，就是這一輪做的事。

### P6.1 列表回應瘦身 ✅

`/games?per_page=20` 回 **102 KB**，其中四分之三是每款遊戲的完整英文描述，還夾帶
enricher 的內部欄位（`zhuoyouku_id`、`subtypes`、`subcategory_ranks`、25 家出版社）。
列表頁是一格一格的卡片，這些欄位一個都沒被讀到。

- `app/api/v1/games.py::LIST_FIELDS`：列表 / 搜尋 / 語意三條路徑都帶 projection。
  `aliases`、`is_expansion`、`quality_score` 留著不是給前端看的，是 `relevance` 要用。
- 詳情頁 `/games/{bgg_id}` 不變，仍回完整文件。
- 結果：列表 102 KB → **45 KB**，搜尋 65 KB → **28 KB**（各 −56%）。

順帶修 `scripts/eval_search.py`：`has_description` 與 `family` 兩個條件本來讀列表回應裡的
`description_en` / `subcategory_ranks`，欄位不再送就變成 0% precision。改成需要時才去
`/games/{bgg_id}` 取那兩個欄位（帶快取）——這樣測的是「這款遊戲真的有描述」，
而不是「回應剛好夾帶了描述」。

### P6.2 中文存的是簡體 ✅

`description_zh` 從 14 筆長到 1,538 筆，但全部是簡體：繁體站的遊戲頁面下面寫著
「给出一个词的线索」。`name_zh` 有走 `to_traditional`，描述沒有。

- `zhuoyouku_enricher` 的寫入路徑補上轉換，斷掉來源。
- `scripts/traditionalize_zh.py`（預設 dry-run，`--apply` 才寫）：轉了 **1,555** 筆。
- `app/core/cjk.py` 的 OpenCC 設定從 `s2t` 換成 `s2tw`。`s2t` 給的是「爲」，
  台灣寫「為」。沒有用 `s2twp`，那會連詞彙一起換（網絡→網路），對遊戲描述來說改過頭了。
- 同一支腳本清掉 enricher 私自鏡射的 9 個欄位（`categories_zh`、`mechanics_zh`、
  `genre_zh`、`designers_zh` …，共 1,524 筆）。標籤的中文名以 `app/core/vocab.py` 為準，
  文件裡那份簡體副本只會跟它打架——CLAUDE.md 早就寫著不要從遊戲文件拿標籤中文名。

### P6.3 中文語意搜尋 ✅

向量索引是 `BAAI/bge-small-en-v1.5`，英文檢索模型。中文句子直接丟進去等於亂數：
實測「適合兩人的合作解謎」回的是 Just One（3–7 人派對）、Café International、
Nothing Personal，三款都不是合作遊戲。

新增 `app/core/zh_query.py`：查詢先讀成英文概念再進向量。字典就是站上已經有的那份——
85 個分類 + 196 個機制各自的中文名——外加一組描述遊戲但不是標籤的日常詞
（人數、長度、輕重、氣氛）。

- 「適合兩人的合作解謎」→ `cooperative two player puzzle solving`
- 「卡牌遊戲 引擎建造」→ `engine building Card Game`
- 「璀璨寶石」→ 對不到任何概念 → **回 None，改走名稱比對**。
  對不到就不要硬送進模型：英文模型讀中文書名只會生出看起來合理的噪音，
  比誠實說一句「這題走名稱比對」更糟。

實測後的前五名：合作解謎那題全部是合作 / 解謎遊戲；引擎建造那題全部是引擎建造；
書名那題第一筆是璀璨寶石本體。

Golden set 從 47 題加到 **51 題**（三題中文語意 + 一題中文書名必須退回名稱比對），
全部通過，recall@10 / top1 / precision@10 都是 100%。

### 這一輪沒動、但確認過的

- **`name_zh` 的天花板已經到了**：BGG 的中文別名對 `users_rated >= 500` 的遊戲查完了
  4,405 筆，一筆都沒有。想再往上只能換來源（出版社官網、社群、翻譯 API），
  這仍然是第 9 節的待決定事項。長尾（`users_rated < 500`）還有 30,387 筆沒查過，
  值得掛背景跑，但預期命中率很低。
- **中文語意搜尋不需要換模型**。原本以為要換多語 retrieval 模型並重建整個 collection
  （維度會變），實際上把查詢翻成概念就解決了，索引一個字都不用動。
