# Phase 0 — 基礎建設 執行計畫

## 目標

搭建完整開發環境骨架：前端 Next.js + 後端 FastAPI + Docker 服務（MongoDB/Qdrant/Redis），OAuth 登入，雙語切換，可本地跑通。

---

## Step 1：Docker Compose 基礎服務

**產出**：`docker-compose.yml`

啟動 3 個服務：
- MongoDB 7（port 27017，掛 volume `./data/mongo`）
- Qdrant（port 6333，掛 volume `./data/qdrant`）
- Redis 7（port 6379，掛 volume `./data/redis`）

**指令**：`docker compose up -d` 驗證三服務皆 running。

---

## Step 2：FastAPI 後端骨架

**產出**：`backend/` 目錄

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI app, CORS, router mount
│   ├── core/
│   │   ├── config.py         # Settings (env vars, DB URLs)
│   │   ├── database.py      # MongoDB client, Qdrant client, Redis client
│   │   └── security.py      # OAuth verification helpers
│   ├── api/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       └── health.py     # GET /api/v1/health → { status: "ok" }
│   └── models/
│       └── __init__.py
├── requirements.txt          # fastapi, uvicorn, motor, qdrant-client, redis, pydantic-settings, python-dotenv, httpx, authlib
├── .env.example              # DB URLs, OAuth client IDs (placeholder)
└── Dockerfile
```

**驗證**：`uvicorn app.main:app --reload` → `/api/v1/health` 回 200。

---

## Step 3：Next.js 前端骨架 + i18n

**產出**：`frontend/` 目錄

```
frontend/
├── src/
│   ├── app/
│   │   ├── layout.tsx        # Root layout with i18n provider
│   │   ├── page.tsx          # Home page (placeholder)
│   │   └── [locale]/
│   │       ├── layout.tsx    # Locale layout
│   │       └── page.tsx      # Locale home
│   ├── components/
│   │   ├── LanguageSwitcher.tsx
│   │   └── Navbar.tsx
│   ├── lib/
│   │   └── api.ts            # FastAPI client (fetch wrapper)
│   ├── i18n/
│   │   ├── config.ts         # i18n config (locales: en, zh)
│   │   ├── en.json           # English translations
│   │   └── zh.json           # Chinese translations
│   └── middleware.ts          # Next.js i18n middleware
├── public/
├── next.config.ts
├── package.json
└── Dockerfile
```

i18n 方案：`next-intl`（App Router 原生支援）。

**驗證**：`npm run dev` → 首頁可切換中英文。

---

## Step 4：OAuth 登入（Google + GitHub）

### 後端
- `backend/app/api/v1/auth.py`
  - `GET /api/v1/auth/google` → redirect to Google OAuth
  - `GET /api/v1/auth/google/callback` → 交換 code → 取 profile → 建立/查用戶 → 發 JWT
  - `GET /api/v1/auth/github` → redirect to GitHub OAuth
  - `GET /api/v1/auth/github/callback` → 同上
- `backend/app/models/user.py` — User document schema（MongoDB）
- JWT token 用 `python-jose`，存 httpOnly cookie

### 前端
- `frontend/src/components/LoginButton.tsx` — Google/GitHub login 按鈕
- `frontend/src/hooks/useAuth.ts` — 取得登入狀態
- Navbar 顯示登入/登出

**驗證**：點 Google 登入 → 跳轉 → 回調 → 前端顯示已登入用戶名。

---

## Step 5：前端 Layout + 公開頁面

**產出**：
- `Navbar` — logo、語言切換、登入按鈕、導航連結
- `Footer` — 簡單 footer
- 首頁 — Hero section（桌遊推薦平台介紹）+ CTA 按鈕（開始探索/問卷推薦）
- 基本路由：`/[locale]/` (home), `/[locale]/games` (placeholder), `/[locale]/survey` (placeholder), `/[locale]/chat` (placeholder)

**驗證**：首頁可見、導航可用、語言切換正常。

---

## Step 6：專案文件

更新 `README.md`：
- 專案介紹
- 技術棧
- 開發環境啟動步驟（docker compose up → backend → frontend）
- 環境變數說明

---

## 執行順序

1. Step 1 (Docker Compose) — 獨立，先跑
2. Step 2 (FastAPI) + Step 3 (Next.js) — 可並行
3. Step 4 (OAuth) — 需 Step 2+3 完成
4. Step 5 (Layout) — 需 Step 3 + Step 4
5. Step 6 (README) — 最後收尾

## 驗證清單

- [ ] `docker compose up -d` → 3 服務 running
- [ ] `GET /api/v1/health` → 200
- [ ] 前端首頁可開、中英切換
- [ ] Google OAuth 登入成功、前端顯示用戶
- [ ] GitHub OAuth 登入成功、前端顯示用戶
- [ ] 未登入可瀏覽所有頁面
