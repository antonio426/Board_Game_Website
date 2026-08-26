# Phase 5 — 數據品質 + BGG 大量資料 執行計畫

## 目標
提升資料品質：範例資料補中文名/描述/圖片、術語翻譯自動化、BGG 大量爬取策略

---

## Step 1：範例資料補全
- csv_importer 的 12 筆 sample data 加上中文名、描述、圖片 URL
- 確保 translate/terms 在 sample data 後自動執行

## Step 2：BGG 大量資料爬取
- 用 BGG XML API2 的 /thing endpoint 按批次爬取 Top 2000
- 加入重試 + 速率限制 + 進度追蹤
- 若 BGG API 仍被擋，改用 BGG dataset (boardgames.csv from Kaggle/BGG)

## Step 3：前端遊戲卡片圖片 fallback
- 圖片為空時用 placeholder SVG
- 列表頁/詳情頁/推薦卡片統一 fallback

## Step 4：Redis 快取層
- 熱門查詢結果快取 (games list, recommendations)
- 快取失效策略

## 執行順序
1. Step 1 — 立即可做
2. Step 3 — 跟 Step 1 一起
3. Step 2 — 需要網路或替代資料源
4. Step 4 — 最後加
