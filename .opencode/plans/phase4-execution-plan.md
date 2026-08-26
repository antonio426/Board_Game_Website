# Phase 4 — 用戶互動 + 部署 執行計畫

## 目標
用戶收藏/評分 UI、個人遊戲庫頁面、部署配置

---

## Step 1：用戶收藏/評分 UI
- 遊戲詳情頁：收藏按鈕 + 評分組件
- 列表頁：收藏圖標快捷
- 前端呼叫 actions API

## Step 2：個人遊戲庫頁面
- `/[locale]/profile` 頁面
- 顯示收藏清單、評分歷史、瀏覽歷史
- 未登入顯示登入提示

## Step 3：後端用戶遊戲庫 API
- `GET /api/v1/collection/me` — 返回用戶收藏+評分
- `DELETE /api/v1/actions/{id}` — 刪除行為記錄

## Step 4：部署配置
- Backend Dockerfile + frontend Dockerfile
- docker-compose 加 frontend/backend 服務
- nginx 反向代理配置
- 環境變數整理

## 執行順序
1. Step 1+2+3 可一起做（用戶互動功能）
2. Step 4 獨立
