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

## 2. Phase 1 — 資料補齊（約 2 天）

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

## 3. Phase 2 — 排序品質（約 2 天）

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

## 4. Phase 3 — 篩選體驗（約 2–3 天）

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

## 5. Phase 4 — 推薦品質（約 3 天）

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

## 6. Phase 5 — 量測（0.5 天，但要先做）

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
