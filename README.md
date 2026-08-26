# Board Game Explorer — 智慧桌遊推薦平台

中英雙語智慧桌遊推薦平台，透過多維度推薦引擎 + AI 對話搜尋 + 引導式問卷，讓桌遊愛好者與新手都能快速找到最適合的桌遊。

## 技術架構

| 層級 | 技術 | 說明 |
|------|------|------|
| 前端 | Next.js 15 (App Router) + next-intl | SSR/SSG、i18n、SEO |
| 後端 API | Python FastAPI | 推薦引擎、爬蟲排程、AI 對話 |
| 資料庫 | MongoDB 7 | 桌遊/評論/用戶結構化資料 |
| 向量庫 | Qdrant | 嵌入搜尋、語意推薦 |
| 快取 | Redis 7 | 熱門查詢、session |

## 快速開始

### 1. 啟動基礎服務

```bash
docker compose up -d
```

啟動 MongoDB (27017)、Qdrant (6333)、Redis (6379)。

### 2. 啟動後端

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # 編輯 .env 填入 OAuth 設定
uvicorn app.main:app --reload
```

後端運行在 http://localhost:8000，API 文件 http://localhost:8000/docs

### 3. 啟動前端

```bash
cd frontend
npm install
npm run dev
```

前端運行在 http://localhost:3000

## 環境變數

| 變數 | 說明 | 預設值 |
|------|------|--------|
| `MONGO_URI` | MongoDB 連線字串 | `mongodb://boardgame:boardgame_dev@localhost:27017` |
| `QDRANT_URL` | Qdrant URL | `http://localhost:6333` |
| `REDIS_URL` | Redis URL | `redis://localhost:6379/0` |
| `GOOGLE_CLIENT_ID` | Google OAuth Client ID | — |
| `GOOGLE_CLIENT_SECRET` | Google OAuth Secret | — |
| `GITHUB_CLIENT_ID` | GitHub OAuth Client ID | — |
| `GITHUB_CLIENT_SECRET` | GitHub OAuth Secret | — |
| `JWT_SECRET` | JWT 簽名密鑰 | `change-this-to-a-random-secret` |
| `FRONTEND_URL` | 前端 URL | `http://localhost:3000` |
| `BACKEND_URL` | 後端 URL | `http://localhost:8000` |

## 專案結構

```
board-game-website/
├── docker-compose.yml        # MongoDB + Qdrant + Redis
├── backend/                  # FastAPI
│   ├── app/
│   │   ├── main.py           # App entry, CORS, routers
│   │   ├── core/             # Config, database, security
│   │   ├── api/v1/           # REST endpoints (health, auth)
│   │   └── models/           # Pydantic / MongoDB models
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
├── frontend/                 # Next.js 15
│   ├── src/
│   │   ├── app/[locale]/     # Locale-routed pages
│   │   ├── components/      # Navbar, Footer, LoginButton
│   │   ├── hooks/           # useAuth
│   │   ├── i18n/            # next-intl config + translations
│   │   └── lib/             # API client
│   └── package.json
└── README.md
```
