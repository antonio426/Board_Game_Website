# UX 改善規劃書 — Board Game Hub

> 目的：盤點現有頁面與使用者流程，列出尚未做但能明顯改善體驗的工作項，按效益/成本排優先順序。
> 對齊對象：`design-system/boardgamehub/MASTER.md`（Felt green + gold on dark、Righteous + Poppins、density 4/10）。

---

## 1. 現況摘要

### 已完成基礎（本 session + 之前）
- 搜尋：精確子字串 + s2t/t2s 展開 + aliases[] 多 CJK 名稱命中
- cjk 政策：寫入端 s2t 轉繁體，enricher 同時寫 aliases
- 圖片：32k 既有 + 11k 新 = 43k 本地圖檔，thumb 49k
- 推薦：hybrid (content-based + collaborative) 走 Redis 300s cache
- 標籤：`/[locale]/tags` 新頁面，列出 85 categories + 196 mechanics = 281 tags
- 詳情頁：categories/mechanics chips 改成 clickable Link

### 已有的頁面與路由
| Route | 功能 |
|---|---|
| `/[locale]/` | 首頁（推薦 + 熱門 + Quick Picks） |
| `/[locale]/games` | 桌遊列表（搜尋 + filter + 分頁） |
| `/[locale]/explore` | 探索（semantic + text search） |
| `/[locale]/games/[id]` | 桌遊詳情 |
| `/[locale]/tags` | 標籤瀏覽（本次新增） |
| `/[locale]/survey` | 問卷推薦 |
| `/[locale]/chat` | AI 對話 |
| `/[locale]/profile` | 我的收藏 |

---

## 2. UX 痛點（按區塊）

### A. 搜尋與探索
- **A1.** `/games` 頁 filter section 預設收合 → 新使用者不知道有篩選功能
- **A2.** `/tags` 頁沒有熱門/推薦區塊 → 281 個 tags 平均呈現，要使用者自己找
- **A3.** 沒有「最近瀏覽」或「繼續瀏覽」紀錄
- **A4.** 沒有「隨機桌遊」按鈕（discovery 樂趣）
- **A5.** 搜尋結果沒有相關性評分或排序依據

### B. 桌遊詳情頁
- **B1.** Categories/mechanics chips 沒 section header（「Tags」標題），視覺上像散落的標籤
- **B2.** 沒有 share 按鈕（copy URL、Web Share API）
- **B3.** 沒有 image lightbox / zoom（點圖放大看規則書細節）
- **B4.** Favorite / Own / Rate 按鈕需登入才顯示 → 未登入使用者沒引導（應顯示登入 CTA）
- **B5.** Similar Games 沒說明推薦依據（「為什麼推薦這款」可加 transparency）
- **B6.** 沒有鍵盤快捷鍵（← → 切換上/下一個）
- **B7.** 沒有 "users_rated" 顯示（data 已有，UI 沒用到）

### C. 列表與篩選
- **C1.** 沒有 AND/OR 多選 tag filter（後端 `categories=A,B` 已支援 `$in`，前端 UI 沒做）
- **C2.** 沒有「排除」filter
- **C3.** 只有分頁，沒有無限捲動 / virtual scroll
- **C4.** 沒有 sort by「新加入」「本地熱門」「bgg_year 範圍」
- **C5.** Filter 組合不能儲存為 preset / share link

### D. 使用者帳號與收藏
- **D1.** 只有 favorite/own/rate，沒有「想玩」狀態
- **D2.** 沒有「遊玩次數」「上次遊玩」紀錄
- **D3.** 沒有自訂清單（user 可以建多個 list 分類管理）
- **D4.** 沒有 export collection（CSV / BGG XML 格式）
- **D5.** 沒有公開 profile / share collection 頁面

### E. 視覺與互動
- **E1.** 沒有 image zoom / lightbox（同 B3）
- **E2.** 沒有 light theme（目前只有 dark）
- **E3.** 沒有字型大小 / accessibility 設定
- **E4.** loading skeleton 可以更精緻
- **E5.** 沒有「回到頂部」按鈕（長列表時）

### F. AI 推薦
- **F1.** Survey 是表單式，可以做成 chat-based
- **F2.** 推薦結果沒說「為什麼推薦這款」
- **F3.** 沒有「I'm feeling lucky」隨機推薦按鈕（同 A4）
- **F4.** AI Chat 不記得 context（每輪 query 都重查）

### G. 社群
- **G1.** 沒有評論 / 留言
- **G2.** 沒有使用者評論（v.s. 只有 BGG 聚合分數）
- **G3.** 沒有「找品味相似的人」/ groups

### H. 效能 / 載入
- **H1.** 詳情頁圖片 lazy load 要驗證
- **H2.** 沒 prefetch（hover 時預先載入下一頁）
- **H3.** 沒 service worker / offline 支援

---

## 3. 優先順序

### Tier 1 — quick wins（1-2 小時 each）
| # | 工作 | 效益 |
|---|---|---|
| T1.1 | **B1** Game detail 加 "Tags" section header | 視覺分組、可讀性 |
| T1.2 | **A4 / F3** 首頁 + `/explore` 加隨機桌遊按鈕 | discovery 樂趣 |
| T1.3 | **B2** Detail page 加 share 按鈕（copy URL） | 社交傳播 |
| T1.4 | **E5** 長列表加「回到頂部」按鈕 | 列表 UX |
| T1.5 | **A1** `/games` filter 預設展開 | 篩選可發現性 |
| T1.6 | **A2** `/tags` 加 featured 區塊 + 按 count desc 排序 | tags 發現性 |

### Tier 2 — medium effort（3-6 小時 each）
| # | 工作 | 效益 |
|---|---|---|
| T2.1 | **B3** Image lightbox / zoom | 細節查看 |
| T2.2 | **C1** AND/OR 多選 tag filter（前端 UI） | 精準篩選 |
| T2.3 | **A3** 「最近瀏覽」紀錄 | 個人化 |
| T2.4 | **B4** 未登入使用者的 favorite CTA 引導 | 轉換率 |
| T2.5 | **F2** 推薦理由說明（「因為你有 X 標籤的收藏」） | 信任感 |
| T2.6 | **B5 / B7** 詳情頁顯示 "bgg users rated" + similar games 理由 | 透明 / 信任 |

### Tier 3 — big effort（1-2 天 each，需先確認優先度）
| # | 工作 | 效益 |
|---|---|---|
| T3.1 | **C6** 比較遊戲 side-by-side | 採購決策 |
| T3.2 | **D3** 自訂清單（多個 list） | 收藏管理 |
| T3.3 | **D4** Export collection（CSV / BGG XML） | 資料可攜 |
| T3.4 | **F1** Chat-based survey | 對話體驗 |
| T3.5 | **F4** Chat 對話記得 context | 對話連貫 |
| T3.6 | **D5** 公開 profile / share collection | 社群分享 |
| T3.7 | **C3** 無限捲動 / virtual scroll | 大量資料 UX |

### 不建議做（除非明確需求）
- **E2** Light theme：dark 已足夠，加 light 要維護兩套
- **E3** Accessibility 細項設定：先做 WCAG AA baseline 即可
- **G 區** 社群功能：需求未驗證，先觀察
- **H3** PWA / offline：mobile-first 不是當前定位

---

## 4. 建議下個 sprint（~6 小時，Tier 1 全做）

挑這 6 項：
1. **T1.1** B1：Game detail 加 "Tags" section header（5 分鐘）
2. **T1.2** A4：首頁 + `/explore` 加隨機桌遊按鈕（30 分鐘）
3. **T1.3** B2：Share 按鈕（copy URL）（20 分鐘）
4. **T1.4** E5：「回到頂部」按鈕（30 分鐘）
5. **T1.5** A1：`/games` filter 預設展開（5 分鐘）
6. **T1.6** A2：`/tags` 加 featured 區塊 + 按 count desc 排序（30 分鐘）

預估總時間：~2 小時
預期效益：搜尋可發現性 +1 個檔次、隨機探索提升使用者驚喜度、分享路徑打通

---

## 5. 中期 Roadmap（sprint+2 之後）

| Sprint | 重點 |
|---|---|
| sprint 2 | T2.1 (lightbox) + T2.6 (similar games 理由 + users_rated) |
| sprint 3 | T2.2 (多選 tag) + T2.4 (未登入 CTA) |
| sprint 4 | T2.3 (最近瀏覽) + T2.5 (推薦理由) |
| sprint 5+ | 依需求從 Tier 3 挑 |

---

## 6. 待你決定

1. **mobile / accessibility 優先度？** H1/E3 等要不要先做？
2. **social features（G 區）** 要進嗎？評論 / 公開 profile
3. **Light mode（E2）** 要不要？目前只支援 dark
4. **deployment / hosting 計畫？** 影響 H3（offline）等是否要做
5. **下個 sprint 確認做 Tier 1 全部 6 項？** 還是只挑部分？

---

## 7. 寫這個規劃時未做但建議補的事

- 跑一次 Lighthouse audit 拿客觀數字
- 用 Playwright + 視覺截圖錄一段新手使用者流程，找真正的痛點
- 問 3-5 個真實使用者做 usability test
- 設 analytics（Mixpanel / Plausible）量化每個 step 的 drop-off
