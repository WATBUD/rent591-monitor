# 591 租屋訂閱監控系統

## 專案目標

自動監控 591 租屋網的多組搜尋條件（訂閱），定期抓取並比對快照，
通知使用者：🆕 新增物件、💰 降價物件、❌ 下架物件。依區域分組呈現。

使用者可透過設定介面（已有 HTML 原型 `ui/591訂閱管理.html`）編輯訂閱條件：
城市、區域（複選）、類型、房數、租金範圍、坪數範圍、型態。

## 建議架構

```
rent591-monitor/
├── CLAUDE.md              # 本文件
├── subscriptions.json     # 訂閱條件設定（seed 已提供）
├── scraper/               # 抓取模組（Python 建議用 httpx + selectolax/bs4）
│   ├── list_scraper.py    # 列表頁抓取（見下方「重要實測發現」）
│   └── detail_scraper.py  # 物件內頁抓取
├── data/
│   └── snapshots/         # 每次抓取的快照 JSON（或改用 SQLite）
├── diff.py                # 快照比對：新增/降價/下架
├── notify.py              # 通知（建議 Telegram Bot 或 Discord Webhook）
├── main.py                # 主流程：讀訂閱 → 抓取 → 比對 → 通知 → 存快照
└── ui/
    └── 591訂閱管理.html    # 訂閱編輯介面原型（window.storage 版，需改接 subscriptions.json）
```

## 591 URL 參數規格（已驗證）

範例：
`https://rent.591.com.tw/list?region=3&sort=posttime_desc&section=43,47,44,26&kind=1&shape=2&price=0$_40000$&layout=4&acreage=30$_$`

| 參數 | 說明 | 值 |
|------|------|-----|
| region | 城市 | 1=台北市, 3=新北市 |
| section | 區域，逗號複選 | 見下方對照表 |
| kind | 類型 | 1=整層住家, 2=獨立套房, 3=分租套房, 4=雅房 |
| shape | 型態，可複選 | 1=公寓, 2=電梯大樓, 3=透天厝, 4=別墅 |
| layout | 房數，可複選 | 1, 2, 3, 4（4=4房以上） |
| price | 租金範圍 | `min$_max$`，開放上限用 `min$_$`，如 `0$_40000$` |
| acreage | 坪數範圍 | 同 price 格式，如 `30$_$`＝30坪以上 |
| sort | 排序 | posttime_desc（最新）, money_asc, money_desc, area_asc, area_desc |
| page | 頁碼 | 對純 HTTP 抓取無效，見下方 |

### 新北市 section 對照（region=3）

26=板橋, 27=汐止, 28=深坑, 34=新店, 37=永和, 38=中和, 39=土城,
40=三峽, 41=樹林, 42=鶯歌, 43=三重, 44=新莊, 45=泰山, 46=林口,
47=蘆洲, 48=五股, 49=八里, 50=淡水

### 台北市 section 對照（region=1）

1=中正, 2=大同, 3=中山, 4=松山, 5=大安, 6=萬華, 7=信義,
8=士林, 9=北投, 10=內湖, 11=南港, 12=文山

## ⚠️ 重要實測發現（2026-08 驗證）

1. **列表頁是 JS 動態渲染**。純 HTTP GET 只能拿到 SSR 的第一頁約 30 筆，
   `page=2` 參數無效（回傳內容與第一頁相同）。
   - 解法 A（首選）：用 Playwright/無頭瀏覽器渲染，可正常翻頁。
   - 解法 B（輕量）：同一條件用多種 sort 各抓一次取聯集，
     結果 < 60 筆時通常能湊齊（實測 37 筆的搜尋可行）。
   - 解法 C：研究 591 的內部 JSON API（列表資料由 XHR 載入，
     需帶 CSRF token / deviceid cookie，欄位最乾淨但較脆弱）。

2. **物件內頁純 HTTP 可抓**（如 `https://rent.591.com.tw/21813196`），資料完整：
   押金、最短租期、身份要求、可否養寵物/開伙、設備清單、屋齡、
   建物面積（不含公設）、權狀坪數、聯絡電話、屋主說明全文。

3. **刊登時間只有相對時間**：內頁顯示「此房屋在12分鐘前發佈」、
   列表顯示「N天前更新」。抓取時需立即換算為絕對日期存檔
   （posted_at ≈ fetch_time - 相對時間），誤差約一天內。

4. **同一物件會被多個仲介重複刊登**（不同 ID、同社區同坪數同樓層）。
   建議用（社區, 坪數, 樓層, 房數）做 fuzzy 分組標記「疑似重複」。

5. **反爬**：請求間隔建議 ≥ 3 秒、帶正常 User-Agent。591 對高頻請求會擋。
   偶發失敗要能重試與跳過，不可讓整輪更新中斷。

## 列表頁可解析欄位

物件 ID（URL 尾碼）、標題、租金、額外費用（「額外費用 1,580元/月」）或
「租金含管理費/車位/清潔費」、格局（4房2廳）、坪數、樓層（7F/24F）、
社區名稱與連結、區域-街道、距離地標（距新埔132公尺）、標籤（近捷運/
可養寵物/可租補/社會住宅/屋主直租…）、刊登者類型與姓氏、更新相對時間、
昨日瀏覽數、降價資訊（「降3000元，下降8.3%」）。

## 資料模型建議

```json
{
  "listing_id": "21813196",
  "subscription_id": "sub-xxx",
  "title": "獨棟華廈電梯四房二衛附冷氣租金含管理費",
  "url": "https://rent.591.com.tw/21813196",
  "region": "新北市", "district": "板橋區", "street": "金門街369巷36號",
  "community": "金龍名邸",
  "price": 33000, "extra_fee": 0, "fee_included": ["管理費"],
  "total_monthly": 33000,
  "rooms": 4, "halls": 2, "baths": 2,
  "size_ping": 40.0, "floor": "4F", "total_floor": "7F",
  "shape": "電梯大樓",
  "tags": ["屋主直租","有電梯","可開伙"],
  "poster_type": "屋主", "poster_name": "廖小姐",
  "deposit": "二個月", "min_lease": "一年", "pet_ok": false,
  "posted_at": "2026-08-11", "first_seen": "2026-08-11",
  "last_seen": "2026-08-11",
  "price_history": [{"date":"2026-08-11","price":33000}],
  "status": "active",
  "user_state": "untracked",
  "note": ""
}
```

衍生欄位：`total_monthly = price + extra_fee`（比較關鍵！有物件租金 33,000
但額外費用 7,000，實際比 38,000 含管理費的更貴）、`price_per_ping`。

## 比對邏輯（diff.py）

以 listing_id 為 key 比對前後快照：
- 新 ID → 🆕 新增
- 同 ID 價格下降 → 💰 降價（記入 price_history）
- 舊 ID 消失 → 標記 missing；連續 2 輪 missing 才判定 ❌ 下架（避免暫時被擋誤判）
- 報告依 district 分組輸出

## 通知

LINE Notify 已於 2025 年停止服務，勿使用。建議：
- Telegram Bot（免費、簡單、支援排版）
- Discord Webhook（最簡單，一個 POST 就好）
- 或本機產生 HTML 報告

## 排程

cron 或 systemd timer，建議每 2~6 小時一輪。每輪流程：
讀 subscriptions.json → 逐訂閱抓列表 → 對新物件抓內頁補細節 →
diff → 通知 → 寫入快照。

## 開發順序建議

1. `list_scraper.py`：先做單一訂閱、單次抓取、輸出 JSON（用多排序聯集法起步）
2. `diff.py` + 快照存檔：跑兩次驗證比對正確
3. `main.py` 串接多訂閱 + 通知
4. 內頁 enrich（僅對新增物件抓內頁，控制請求量）
5. 之後再考慮 Playwright 翻頁、重複刊登偵測、Web UI 接後端
