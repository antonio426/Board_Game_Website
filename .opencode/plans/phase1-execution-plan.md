# Phase 1 — BGG 資料爬取 + 展示 執行計畫

## 目標
BGG 爬蟲抓取桌遊資料 → MongoDB 儲存 → 後端 API → 前端列表/詳情頁展示

---

## Step 1：BGG 爬蟲核心（Scrapy + XML API2）
- Scrapy spider：BGG XML API2 `/thing` + `/search`
- Rate limit：2 req/s，指數退避
- 資料：名稱、描述、人數、時間、年齡、評分、rank、weight、categories、mechanics、expansions、series、designers、publishers
- 存入 MongoDB `board_games` collection
- 增量爬蟲：首次全量 Top 2000（by rank），之後增量

## Step 2：圖片下載本地化
- 異步下載縮圖 + 原圖
- 存 `backend/data/images/{bgg_id}/`
- MongoDB 記錄本地路徑

## Step 3：擴充/系列關係解析
- 解析 BGG `<link type="boardgameexpansion">` + `<link type="boardgamecompilation">`
- 寫入 BoardGame document 的 expansions / series 欄位

## Step 4：桌遊列表 API
- `GET /api/v1/games` — 分頁、篩選（人數/時間/難度/類別/機制）、排序（rating/rank/name）
- `GET /api/v1/games/{bgg_id}` — 單一桌遊詳情

## Step 5：桌遊列表頁（前端）
- 篩選 sidebar（人數、時間、難度、類別、機制）
- 排序 dropdown
- 卡片 grid 顯示

## Step 6：桌遊詳情頁（前端）
- 圖片、中英描述、評分、機制/類別標籤
- 擴充/系列導航
- 相似遊戲推薦區塊（placeholder）

## Step 7：中文資料 + 嵌入向量（P1，可後續）
- AI 批量翻譯描述
- 嵌入向量生成 → Qdrant

## 執行順序
1. Step 1-3 可串行（爬蟲 → 圖片 → 關係解析）
2. Step 4 需要 Step 1 完成
3. Step 5-6 需要 Step 4 完成
4. Step 7 獨立，Phase 1 末尾
