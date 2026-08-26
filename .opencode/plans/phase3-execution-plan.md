# Phase 3 — 問卷推薦 + AI 對話 + 中文翻譯 執行計畫

## 目標
問卷推薦頁（偏好收集→推薦結果）、AI 對話推薦（LLM 串接）、中文描述翻譯、嵌入向量

---

## Step 1：問卷推薦頁
- 前端多步問卷：人數偏好 → 遊戲時長 → 難度偏好 → 類別/機制多選
- 提交後呼叫 `GET /recommendations/context` 或 `GET /recommendations/for-me`
- 結果頁：推薦遊戲卡片 + 理由標籤

## Step 2：AI 對話推薦
- 後端：`POST /api/v1/chat/recommend` 接收使用者訊息
- 整合 LLM：用遊戲資料 context + 推薦引擎結果 → 自然語言回覆
- 前端：chat UI（訊息氣泡 + 快捷問題按鈕）

## Step 3：中文描述批量翻譯
- 後端：`POST /api/v1/crawl/translate` 批量翻譯 description_en → description_zh
- 用 LLM API 翻譯（或本地免費翻譯 API）
- 保留原文，翻譯寫入 description_zh 欄位

## Step 4：Qdrant 嵌入向量
- 遊戲描述 → embedding（sentence-transformers 或 LLM embedding）
- 寫入 Qdrant collection
- 推薦 API 加入語意搜尋端點

## 執行順序
1. Step 1 (問卷) — 獨立前端功能
2. Step 2 (AI 對話) — 需 LLM API
3. Step 3 (翻譯) — 需 LLM API，可與 Step 2 共用
4. Step 4 (嵌入) — 可在翻譯後做
