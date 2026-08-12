# 實作計畫 — 591 租屋訂閱監控系統

> 本文件為實作前的規劃基準，配合 `CLAUDE.md`（完整規格）閱讀。
> 決策已於規劃階段拍板，實作時如需偏離請先更新本文件。

## 最終定案

| 項目 | 決定 |
|---|---|
| 部署 | **GitHub Actions cron + GitHub Pages（全靜態）** |
| 排程 | GitHub Actions `schedule: cron`，每幾小時一輪 |
| 列表抓取 | 多排序聯集（純 HTTP，httpx + selectolax） |
| 訂閱編輯 / 加入關注 | UI 透過 **GitHub API** 一鍵讀寫 repo（fine-grained token 存瀏覽器） |
| 通知 | Telegram Bot |
| 快照 | JSON 檔（每輪時間戳一個 + `data/latest.json` 供頁面讀） |
| 關注清單 | `watchlist.json`（UI 寫、爬蟲讀，關注物件納入持續追蹤/通知） |

### 為何選全靜態 + GitHub API 寫回（放棄 FastAPI 後端）
- 核心需求是「定時跑 + 免費 + 個人自用」，GitHub Actions cron 每項都命中。
- 「一鍵新增/編輯訂閱、加入關注、跨裝置同步」改由 UI 直接呼叫 **GitHub REST API（contents）** 寫回 repo 達成，不需要常駐後端。
- 全靜態無需保活伺服器，維運成本最低（Rule 2 簡單優先）。

## 架構與資料流

```
┌─ GitHub Actions（.github/workflows/monitor.yml, cron 每N小時）──────┐
│  1. checkout repo                                                   │
│  2. pip install -r requirements.txt                                 │
│  3. python main.py                                                  │
│       讀 subscriptions.json                                         │
│       逐訂閱 → list_scraper（多排序聯集）→ diff（比對上輪快照）      │
│       → notify（Telegram 推播 🆕/💰/❌）                             │
│       → 寫 data/snapshots/<ts>.json + data/latest.json              │
│  4. git commit & push 回 repo   ← 也讓排程不因閒置被停用             │
│  Telegram Token 從 GitHub Secrets 注入（不進 repo）                 │
└─────────────────────────────────────────────────────────────────────┘
                                │ commit
                                ▼
┌─ GitHub Pages（靜態）──────────────────────────────────────────────┐
│  ui/591訂閱管理.html                                                │
│   · 讀：GitHub API 抓 subscriptions.json / watchlist.json           │
│         + fetch('data/latest.json') 顯示各區狀態                     │
│   · 寫：新增/編輯訂閱、點「關注」→ GitHub API contents 一鍵 commit   │
│         （fine-grained token 存瀏覽器 localStorage，只授權本 repo）  │
│   · 寫回只影響「下一輪」排程；當輪不會即時重跑爬蟲                   │
└─────────────────────────────────────────────────────────────────────┘
```

> **時序注意**：UI 改訂閱後，要等下一次 cron 觸發才會套用新條件。若想即時，可另加
> `workflow_dispatch` 手動觸發，或監聽 push 觸發（列為後續選項，非 MVP）。

## 檔案結構

```
rent591-monitor/
├── subscriptions.json              # 訂閱設定（notify token 留空，實際從 Secrets 來）
├── watchlist.json                  # 關注清單（UI 寫、爬蟲讀）：listing_id → {note, added_at}
├── requirements.txt                # httpx, selectolax（Telegram 直接用 httpx 打 Bot API）
├── config.py                       # 對照表、路徑、UA、請求間隔
├── scraper/
│   ├── url_builder.py              # subscription → 591 URL（純函式）
│   ├── list_parser.py              # HTML → listing dicts（純解析、可測）
│   └── list_scraper.py             # 多排序聯集 + 去重 + 相對時間換算 + 重試
├── diff.py                         # 前後快照比對，依 district 分組
├── notify.py                       # Telegram 推播（token 讀 env）
├── main.py                         # cron 入口，串接全流程
├── data/
│   ├── snapshots/                  # <timestamp>.json 每輪快照
│   └── latest.json                 # 給 Pages 讀的最新狀態
├── ui/591訂閱管理.html              # 改：window.storage → GitHub API 讀寫 + fetch latest.json
├── .github/workflows/monitor.yml   # cron 排程
└── tests/                          # list_parser fixture 測試
```

## 模組職責

- **url_builder.py**：純函式無 I/O。subscription → URL。`sections` 逗號串接；`price`/`acreage` 產 `min$_max$`（null 上限→`$`）；`layout`/`shape` 逗號複選；`sort` 可覆寫。
- **list_parser.py**：輸入 HTML 字串輸出 listing dict list。抽 CLAUDE.md「列表頁可解析欄位」，衍生 `total_monthly = price + extra_fee`。用固定 HTML fixture 測試。
- **list_scraper.py**：對同一訂閱用多種 sort（posttime_desc / money_asc / money_desc / area_asc / area_desc）各抓一次，以 `listing_id` 取聯集去重。請求間隔 ≥ 3 秒、正常 UA、失敗重試後跳過不中斷。抓取當下即時換算 `posted_at ≈ fetch_time − 相對時間`。log 出各 sort 筆數與聯集總數。
- **diff.py**：以 `listing_id` 比對前後快照。新 ID→🆕；同 ID 降價→💰（記 price_history）；舊 ID 消失→標 missing，連續 `missing_rounds_before_removed`（預設 2）輪才判 ❌ 下架。輸出依 district 分組。
- **notify.py**：Telegram Bot API，token 讀環境變數。分區塊排版訊息。
- **main.py**：讀 subscriptions.json（僅 enabled）+ watchlist.json → 逐訂閱抓 → 載入上輪快照 → diff → notify（含關注物件的降價/下架）→ 寫本輪快照 + latest.json。
- **ui/591訂閱管理.html（Web 寫回）**：
  - 讀：GitHub contents API 取 `subscriptions.json`、`watchlist.json`；`fetch` 取 `data/latest.json` 顯示。
  - 寫：新增/編輯訂閱、點「關注」→ 以 contents API `PUT`（帶目前 blob SHA）commit 回 repo。
  - token：fine-grained PAT，僅授權本 repo 的 Contents 讀寫，存瀏覽器 localStorage、可隨時撤銷。
  - 衝突處理：寫入前先取最新 SHA；若 409（爬蟲剛 commit）重取後重試。

## 憑證處理（重要）
- **Telegram Bot Token**：不寫進 repo、不放前端。存 GitHub → Settings → Secrets，workflow 以環境變數注入 `notify.py`。`subscriptions.json` 裡 token 欄位保持空字串。
- **GitHub PAT（供 UI 寫回）**：
  - 用 **fine-grained token**，只勾選「本 repo」的 **Contents: Read and write**，不要給全帳號權限。
  - 建議 repo 設為 **private**，token 存瀏覽器 localStorage，**絕不 commit 進 repo**。
  - 頁面不得載入任何第三方腳本（降低 token 被竊風險）；token 可隨時在 GitHub 撤銷/重簽。
  - 此 token 僅存在你自己的瀏覽器，不會提供給任何協作工具或寫入專案檔。

## 建置與驗證順序（每步有成功標準）

| # | 模組 | 成功標準 |
|---|---|---|
| 1 | url_builder | sub-001 產出 URL 與 CLAUDE.md 範例參數一致 |
| 2 | list_parser | 對固定 HTML fixture 解析出正確筆數與關鍵欄位 |
| 3 | list_scraper | sub-001 實跑，log 各 sort 筆數與聯集總數 |
| 4 | diff + 快照 | 連跑兩輪驗證 🆕/💰/❌ 判定正確 |
| 5 | notify | Telegram 收到分區訊息 |
| 6 | main | 端到端跑通、產出 latest.json；讀 watchlist.json 生效 |
| 7 | workflow + Pages | Actions 定時跑成功並 commit；Pages 顯示狀態 |
| 8 | UI 寫回 | 貼 token 後，新增/編輯訂閱、點關注能成功 commit 回 repo |

## 風險與已知限制（Rule 12 先講）
1. **591 可能擋 Azure/Actions 機房 IP**。備案：改自架 runner 跑本機。第 3 步實跑即可驗證。
2. **多排序聯集只湊得到 SSR 可見範圍**，>60 筆搜尋抓不全；屆時 log 明講抓到幾筆、不假裝抓全。要抓全需之後上 Playwright。
3. **相對時間換算**有約一天內誤差（CLAUDE.md 已載明）。
4. **排程閒置停用**：GitHub 對長期無活動的 repo 會停用 scheduled workflow；每輪 commit 快照即算活動，可自我維持。
5. **UI 寫回的 token 放在瀏覽器**：授權範圍限本 repo Contents，風險可控但非零；務必 private repo + fine-grained + 可隨時撤銷。
6. **UI 改訂閱不即時生效**：要等下一輪 cron；如需即時再加 `workflow_dispatch`（後續選項）。

## 採用的預設（未逐一詢問）
- 快照存 JSON（非 SQLite）。
- missing 計數存在快照內每筆欄位（非獨立 state 檔）。
- MVP 不抓內頁；第二階段才對「新增物件」抓內頁 enrich，以控制請求量。
- 重複刊登偵測（社區/坪數/樓層/房數 fuzzy 分組）列為後續階段。

## 後續階段（MVP 之後）
1. 內頁 enrich（僅對新增物件）。
2. 重複刊登偵測與標記。
3. 若被 IP 封或需抓 >60 筆：上 Playwright 翻頁或自架 runner。
