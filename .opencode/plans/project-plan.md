# Board Game Website — 專案規劃表

## 1. 專案願景

中英雙語智慧桌遊推薦平台——透過多維度推薦引擎 + AI 對話搜尋 + 引導式問卷，讓桌遊愛好者與新手都能快速找到最適合的桌遊。

---

## 2. 技術架構

| 層級 | 技術 | 說明 |
|------|------|------|
| 前端 | Next.js 15 (App Router) | SSR/SSG、i18n、SEO |
| 後端 API | Python FastAPI | 推薦引擎、爬蟲排程、AI 對話 |
| 資料庫 | MongoDB | 桌遊/評論/用戶結構化資料 |
| 向量庫 | Qdrant 或 Milvus | 嵌入搜尋、語意推薦 |
| 快取 | Redis | 熱門查詢、session |
| AI 對話 | 待定（見 §7 比較表） | 自然語言搜尋 + 推薦 |
| 部署 | 本地 Docker Compose → 後續雲端 | 開發階段本地 |

---

## 3. 功能模組規劃

### 3.1 會員系統（漸進式 + 社群登入）

| 功能 | 說明 | 優先級 |
|------|------|--------|
| 瀏覽不需登入 | 瀏覽桌遊、問卷推薦、AI 對話皆可匿名 | P0 |
| 社群 OAuth 登入 | Google / GitHub OAuth | P0 |
| Email 註冊（可選） | 備用登入方式 | P1 |
| 個人偏好設定 | 標籤選擇、語言偏好 | P0 |
| 收藏清單 | 想玩 / 已擁有 / 最愛 | P1 |
| 瀏覽紀錄追蹤 | 自動記錄瀏覽、停留時間、點擊行為 | P1 |

### 3.2 桌遊資料系統

| 功能 | 說明 | 優先級 |
|------|------|--------|
| BGG 全量爬蟲 | 完整抓取遊戲資料、評分、圖片本地化 | P0 |
| 擴充/系列關係 | BGG 連結的擴充包、系列家族 | P0 |
| 類別/機制標籤 | BGG categories + mechanics 完整映射 | P0 |
| 圖片本地存儲 | 縮圖 + 高清圖本地存，避免外連 | P0 |
| 中英雙語資料 | 桌遊名稱中英並存，描述中英對照 | P0 |
| 中文評論 | 自建中文評論系統 + 爬中文桌遊社群(PTT/巴哈等) | P1 |
| 英文評論 | BGG 評論抓取存儲 | P1 |
| 資料增量更新 | 定期排程更新 BGG 新遊戲/評分變動 | P2 |

### 3.3 推薦引擎

| 演算法 | 參數來源 | 說明 | 優先級 |
|--------|----------|------|--------|
| Content-Based Filtering | 桌遊特徵向量（機制/主題/難度/人數/時間） | 餘弦相似度，同類推薦 | P0 |
| Collaborative Filtering | 用戶評分、瀏覽行為、收藏 | 相似用戶推薦 | P0 |
| Hybrid (加權混合) | 結合上述 + 情境篩選 | 動態加權，依情境調整 | P0 |
| Cold Start — 問卷引導 | 問卷回答 → 偏好標籤 | 新用戶冷啟動 | P0 |
| Cold Start — Onboarding Tags | 註冊時選喜好標籤 | 快速建立初始模型 | P1 |
| 瀏覽行為加權 | 瀏覽時長、點擊頻率、搜尋關鍵字 | 隱性反饋融入推薦 | P1 |

**推薦參數清單：**

| 參數類型 | 具體參數 | 權重方向 |
|----------|----------|----------|
| 用戶評分 | 用戶對桌遊的 1-10 評分 | 高 |
| 瀏覽時長 | 停留在桌遊詳情頁的秒數 | 中 |
| 瀏覽頻次 | 重覆瀏覽同一桌遊次數 | 中 |
| 收藏行為 | 加入想玩/最愛清單 | 高 |
| 搜尋關鍵字 | 搜尋的機制/主題關鍵字 | 中 |
| 桌遊類別 | BGG category 標籤匹配 | 高 |
| 桌遊機制 | BGG mechanism 標籤匹配 | 高 |
| 遊玩人數 | 用戶偏好人數範圍 vs 桌遊支援人數 | 高 |
| 遊玩時間 | 用戶可用時間 vs 桌遊預計時長 | 中 |
| 難度/BGG Weight | 用戶偏好難度 vs 桌遊 complexity | 高 |
| 擴充關係 | 喜歡基礎遊戲 → 推薦擴充 | 中 |
| 系列關係 | 喜歡系列某作 → 推薦同系列 | 中 |
| 評論情感 | 評論正面/負面情感分析 | 低 |

### 3.4 AI 對話搜尋桌遊

| 功能 | 說明 | 優先級 |
|------|------|--------|
| 自然語言理解 | 「我想要 4 人派對遊戲，30 分鐘內」→ 結構化查詢 | P0 |
| 多輪對話推薦 | 追問喜好、逐步收斂推薦範圍 | P0 |
| 中英雙語對話 | 依用戶語言偏好回應 | P1 |
| 對話記憶 | 保持上下文，引用之前提過的偏好 | P1 |
| 推薦理由生成 | 「因為你喜歡 Catan，推薦 Concordia 因為…」 | P2 |

### 3.5 問卷推薦系統

| 模式 | 題數 | 內容 | 優先級 |
|------|------|------|--------|
| 快速問卷 | ~10 題 | 人數、時間、難度、主題偏好、互動類型、競合偏好等 | P0 |
| 詳細問卷 | 20+ 題 | 上述 + 美術風格、策略深度、運氣 vs 技巧、合作 vs 競爭、學習曲線、重玩性等 | P1 |

**快速問卷設計（10 題）：**

| # | 問題 | 選項形式 | 對應推薦參數 |
|---|------|----------|-------------|
| 1 | 通常幾個人玩？ | 單選 (1-2 / 3-4 / 5+ / 不定) | 遊玩人數 |
| 2 | 單局希望多久？ | 單選 (<30min / 30-60 / 60-120 / 2hr+) | 遊玩時間 |
| 3 | 遊戲難度偏好？ | 量表 (輕鬆→硬核) | BGG Weight |
| 4 | 喜歡的主題？ | 多選 (奇幻/科幻/歷史/經濟/派對/恐怖/抽象) | 類別 |
| 5 | 喜歡的互動方式？ | 多選 (競爭/合作/半合作/談判/隱藏身分) | 機制 |
| 6 | 運氣 vs 策略？ | 量表 (純運氣→純策略) | 機制篩選 |
| 7 | 喜歡哪種決策？ | 多選 (工人放置/牌庫構築/區域控制/拍賣/擲骰) | 機制 |
| 8 | 學習曲線接受度？ | 量表 (秒懂→願意讀規則書) | BGG Weight |
| 9 | 重玩性重要嗎？ | 量表 (玩一次就夠→想玩百次) | 變化度 |
| 10 | 有喜歡的桌遊嗎？ | 自由輸入 | Content-Based 起始點 |

### 3.6 桌遊瀏覽與展示

| 功能 | 說明 | 優先級 |
|------|------|--------|
| 桌遊詳情頁 | 圖片、中英描述、規則速查、機制/類別標籤、評分 | P0 |
| 擴充/系列導航 | 顯示擴充包、同系列遊戲 | P0 |
| 篩選排序 | 人數/時間/難度/類別/評分 | P0 |
| 中英 UI 切換 | i18n 雙語介面 | P0 |
| 相似遊戲推薦 | 詳情頁下方「相似遊戲」區塊 | P1 |
| 評論區 | 中英評論、情感分析標記 | P2 |

---

## 4. BGG 全量爬蟲設計

### 4.1 資料抓取範圍

| 資料 | 來源 | 格式 | 備註 |
|------|------|------|------|
| 遊戲基本資訊 | BGG XML API2 `/thing` | XML→JSON | 名稱、描述、人數、時間、年齡、BGG ID |
| 評分統計 | BGG XML API2 `/thing` stats=1 | XML→JSON | 平均分、投票數、rank、weight |
| 類別 & 機制 | BGG XML API2 `/thing` | XML→JSON | categories, mechanics |
| 擴充/系列 | BGG XML API2 `/thing` links | XML→JSON | expansions, compilations, series |
| 圖片 | BGG XML API2 `/thing` + 直接下載 | JPEG/PNG | 縮圖 + 原圖存本地 |
| 英文評論 | BGG XML API2 `/thing` comments | XML→JSON | 分頁抓取 |
| 遊戲列表 | BGG XML API2 `/search` | XML→JSON | 全量 ID 清單 |

### 4.2 爬蟲架構

```
[BGG API/HTML] → [Scrapy/Crawl Scheduler] → [Parser] → [MongoDB]
                                                    ↓
                                              [Image Downloader] → [Local Storage]
                                                    ↓
                                              [Embedding Generator] → [Vector DB]
```

- **排程**：Respect BGG rate limit（~2 req/s），指數退避
- **增量**：首次全量，之後每日只更新 rank/評分變動的遊戲
- **圖片**：異步下載，存本地 `data/images/{bgg_id}/`
- **中文資料**：額外爬中文桌遊社群 + AI 批量翻譯遊戲描述

---

## 5. 推薦系統架構

```
┌─────────────────────────────────────────────────────┐
│                   Recommendation API                 │
├────────────┬─────────────┬──────────────┬───────────┤
│  Content   │ Collaborative│   Hybrid     │   AI      │
│  -Based    │  Filtering   │  Weighted    │  Chat     │
│            │              │  Blend       │  Rec      │
├────────────┴─────────────┴──────────────┴───────────┤
│              Feature Engineering Layer               │
│  ┌──────┬──────┬───────┬──────┬──────┬──────────┐  │
│  │機制  │類別  │人數   │時間  │難度  │情感分析  │  │
│  └──────┴──────┴───────┴──────┴──────┴──────────┘  │
├─────────────────────────────────────────────────────┤
│              User Behavior Tracking                  │
│  瀏覽時長 │ 點擊頻次 │ 收藏 │ 評分 │ 搜尋關鍵字  │
├─────────────────────────────────────────────────────┤
│              Data Layer                              │
│  [MongoDB]          [Vector DB]          [Redis]    │
│  遊戲/用戶/評論      嵌入向量/語意搜      快取/session│
└─────────────────────────────────────────────────────┘
```

---

## 6. 資料模型（MongoDB）

### BoardGame Collection
```json
{
  "bgg_id": 174430,
  "name_en": "Gloomhaven",
  "name_zh": "幽港鎮",
  "description_en": "...",
  "description_zh": "...",
  "image": "/images/174430/thumb.jpg",
  "images": ["/images/174430/1.jpg"],
  "year_published": 2017,
  "min_players": 1,
  "max_players": 4,
  "min_playtime": 60,
  "max_playtime": 120,
  "min_age": 14,
  "bgg_rating": 8.7,
  "bgg_rank": 1,
  "bgg_weight": 3.86,
  "categories": ["Thematic", "Adventure"],
  "mechanics": ["Cooperative", "Action Points", "Card Drafting"],
  "expansions": [{"bgg_id": 199692, "name": "Forgotten Circles"}],
  "series": [{"bgg_id": 243523, "name": "Gloomhaven: Jaws of the Lion"}],
  "designers": ["Isaac Childres"],
  "publishers": ["Cephalofair Games"],
  "created_at": "2026-01-01",
  "updated_at": "2026-08-24"
}
```

### Review Collection
```json
{
  "board_game_bgg_id": 174430,
  "user_id": "uuid",
  "language": "zh",
  "rating": 9,
  "title": "最佳合作遊戲",
  "content": "...",
  "source": "platform",
  "sentiment_score": 0.85,
  "created_at": "2026-08-24"
}
```

### UserProfile Collection
```json
{
  "user_id": "uuid",
  "auth_provider": "google",
  "email": "user@example.com",
  "display_name": "Player1",
  "preferred_language": "zh",
  "preferences": {
    "player_count_range": [3, 4],
    "playtime_range": [60, 120],
    "weight_range": [2.0, 4.0],
    "liked_categories": ["Thematic", "Strategy"],
    "liked_mechanics": ["Worker Placement", "Deck Building"]
  },
  "browse_history": [{"bgg_id": 174430, "duration_sec": 180, "timestamp": "..."}],
  "collections": {"wishlist": [], "owned": [], "favorites": []},
  "created_at": "2026-01-01"
}
```

---

## 7. AI 對話模型比較

| 方案 | 優點 | 缺點 | 適用場景 | 成本 |
|------|------|------|----------|------|
| **OpenAI GPT-4o** | 品質穩定、function calling、多語好 | 每次呼叫付費、依賴外部 | 對話推薦、function calling 查遊戲 | ~$0.005/1K tokens |
| **Anthropic Claude** | 長上下文、安全 | 較貴、function calling 較新 | 長對話、分析型推薦 | ~$0.008/1K tokens |
| **Qwen2.5-72B** | 中英雙語強、開源可自架 | 需 GPU、推理品質略低 | 中英對話、成本敏感 | 自架 GPU 成本 |
| **Llama 3.1 70B** | 開源、社群大 | 中文較弱 | 英文為主的場景 | 自架 GPU 成本 |
| **混合方案** | 簡單意圖→向量搜尋(免費)，複雜對話→LLM API | 架構較複雜 | 最佳成本效益 | 低~中 |

**建議**：P0 用混合方案（向量搜尋 + OpenAI GPT-4o-mini），之後評估自架 Qwen 降低成本。

---

## 8. 開發階段規劃

### Phase 0 — 基礎建設（2 週）
- [ ] Next.js 專案初始化 + i18n 設定
- [ ] FastAPI 專案初始化 + MongoDB + 向量庫連接
- [ ] Docker Compose 開發環境（MongoDB + Qdrant + Redis）
- [ ] OAuth 登入（Google/GitHub）
- [ ] 基本前端 layout + 雙語切換
- [ ] 瀏覽不需登入的公開頁面

### Phase 1 — BGG 資料爬取 + 展示（3 週）
- [ ] BGG 全量爬蟲（遊戲資料 + 評分 + 類別/機制）
- [ ] 圖片下載本地化
- [ ] 擴充/系列關係解析
- [ ] 桌遊列表頁（篩選排序）
- [ ] 桌遊詳情頁（圖片、描述、評分、機制標籤）
- [ ] 中文桌遊社群爬蟲（PTT/巴哈等）
- [ ] 嵌入向量生成 + 存入向量庫

### Phase 2 — 推薦引擎核心（3 週）
- [ ] Content-Based Filtering（特徵向量 + 相似度）
- [ ] 用戶行為追蹤（瀏覽時長、點擊、收藏）
- [ ] Collaborative Filtering（評分矩陣）
- [ ] Hybrid 加權混合 + 情境篩選
- [ ] 推薦 API 端點
- [ ] 詳情頁「相似遊戲」區塊

### Phase 3 — 問卷推薦（2 週）
- [ ] 快速問卷（10 題）UI + 推薦邏輯
- [ ] 詳細問卷（20+ 題）UI + 推薦邏輯
- [ ] 問卷結果 → 用戶偏好模型寫入
- [ ] 問卷結果頁（推薦清單 + 推薦理由）

### Phase 4 — AI 對話搜尋（3 週）
- [ ] 對話 UI 介面
- [ ] 意圖分類（簡單查詢→向量搜；複雜→LLM）
- [ ] LLM 對話 + function calling 查遊戲
- [ ] 多輪對話記憶
- [ ] 中英雙語對話

### Phase 5 — 評論 + 偏好完善（2 週）
- [ ] 用戶評論系統（中英）
- [ ] 評論情感分析
- [ ] 偏好設定頁面
- [ ] 收藏清單（想玩/已擁有/最愛）
- [ ] 瀏覽紀錄頁面

### Phase 6 — 優化 + 上線（2 週）
- [ ] 推薦 A/B 測試框架
- [ ] 推薦效果評估指標（Precision@K, NDCG）
- [ ] 效能優化（Redis 快取、CDN）
- [ ] 部署規劃（雲端方案評估）
- [ ] SEO + 社群分享

**總計：~17 週（4 個月）**

---

## 9. 目錄結構（初步）

```
board-game-website/
├── frontend/                 # Next.js
│   ├── src/
│   │   ├── app/             # App Router pages
│   │   ├── components/      # UI components
│   │   ├── lib/             # API client, utils
│   │   ├── i18n/            # 中英翻譯檔
│   │   └── hooks/           # React hooks
│   ├── public/
│   └── package.json
├── backend/                  # FastAPI
│   ├── app/
│   │   ├── api/             # REST endpoints
│   │   ├── models/          # MongoDB models
│   │   ├── services/        # 推薦、搜尋、爬蟲邏輯
│   │   ├── recommenders/    # 推薦演算法
│   │   ├── crawlers/        # BGG + 中文社群爬蟲
│   │   ├── ai/              # LLM 對話、意圖分類
│   │   └── core/            # Config, auth, db
│   ├── data/                # 本地資料存儲
│   │   ├── images/          # 桌遊圖片
│   │   └── embeddings/      # 嵌入向量快取
│   └── requirements.txt
├── docker-compose.yml
└── README.md
```

---

## 10. 風險與待確認

| 項目 | 風險 | 緩解 |
|------|------|------|
| BGG 爬蟲限流 | IP 被封、資料量大 | 指數退避、分散式排程、備用 IP |
| 中文評論冷啟動 | 初期中文評論很少 | AI 翻譯 BGG 評論填充 + 引導用戶留評 |
| 推薦冷啟動 | 新用戶/新遊戲無行為資料 | 問卷 + onboarding tags 快速建模 |
| 向量庫選擇 | Qdrant vs Milvus 取捨 | P0 先用 Qdrant（輕量），量大再遷移 |
| AI 成本 | LLM API 呼叫費用 | 混合方案 + 快取常見對話模式 |
| 圖片存儲 | 本地磁碟佔用大 | 初期本地，上線後切 S3/OSS |
| BGG 版權 | 圖片/資料商用授權 | 資料僅做推薦展示，不轉售；確認 ToS |

---

## 11. 待使用者確認項目

1. **問卷題目設計** — 10 題快速版 + 20 題詳細版，是否需要調整方向或增加特定問題？
2. **中文社群爬蟲** — PTT 桌遊板 + 巴哈桌遊版之外，還有想爬的來源嗎？
3. **推薦參數權重** — 初版先用均等權重，上線後依 A/B 測試調整，可接受？
4. **AI 模型選擇** — 建議 P0 混合方案（向量搜 + GPT-4o-mini），成本/品質平衡，認同？
5. **桌遊名稱中譯** — 無官方中譯的遊戲，用 AI 翻譯還是保留英文？
6. **MVP 範圍** — Phase 0-2 可否作為第一版 MVP 先上線？
