# Phase 2 — 推薦引擎核心 執行計畫

## 目標
實作 Content-Based + Collaborative Filtering + Hybrid 推薦引擎，用戶行為追蹤，推薦 API

---

## Step 1：用戶行為追蹤系統
- MongoDB `user_actions` collection（瀏覽、點擊、收藏、評分）
- API: `POST /api/v1/actions` 記錄行為，`GET /api/v1/actions/me` 查詢
- 前端: 頁面停留時間追蹤 + 自動上報

## Step 2：Content-Based Filtering
- 特徵向量：categories + mechanics + weight + player count + playtime → one-hot + normalized
- 餘弦相似度計算 `cosine_similarity(vec_a, vec_b)`
- 推薦：給定一個 game_id，找 top-K 最相似遊戲

## Step 3：Collaborative Filtering
- 用戶-遊戲評分矩陣（含隱性反饋：瀏覽時長、收藏加權）
- item-based CF：計算遊戲間相似度（基於共同用戶行為）
- cold start：新用戶用 onboarding tags + 問卷結果

## Step 4：Hybrid 推薦 + 情境篩選
- 加權混合：α * content_score + (1-α) * cf_score
- 情境篩選：人數、時間、難度約束
- 動態加權：有行為數據時偏向 CF，新用戶偏向 CB

## Step 5：推薦 API 端點
- `GET /api/v1/recommendations/similar/{bgg_id}` — Content-Based 相似遊戲
- `GET /api/v1/recommendations/for-me` — 個人化推薦（需登入）
- `GET /api/v1/recommendations/context` — 情境推薦（人數/時間/難度）

## Step 6：前端整合
- 詳情頁相似遊戲改用推薦 API
- 首頁「為你推薦」區塊
- 行為追蹤自動化

## 執行順序
1. Step 1 (行為追蹤) — 基礎，其他推薦依賴
2. Step 2 (CB) + Step 3 (CF) — 可並行概念設計，但程式碼順序建
3. Step 4 (Hybrid) — 需 Step 2+3
4. Step 5 (API) — 需 Step 4
5. Step 6 (前端) — 需 Step 5
