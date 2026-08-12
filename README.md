# 591 租屋訂閱監控系統

自動監控 591 租屋網的多組搜尋條件，定期抓取並比對，通知 🆕 新增 / 💰 降價 / ❌ 下架。
部署於 **GitHub Actions（排程爬蟲）+ GitHub Pages（網頁）**，全靜態、免費、免維運。

詳細規劃見 [`PLAN.md`](PLAN.md)、規格見 [`CLAUDE.md`](CLAUDE.md)。

## 架構

```
GitHub Actions (cron 每 3 小時)          GitHub Pages (靜態)
  main.py                                 ui/591訂閱管理.html
   讀 subscriptions.json + watchlist.json  讀 data/latest.json 顯示狀態
   → 多排序聯集抓 591 → diff → 通知         寫回 subscriptions/watchlist（GitHub API）
   → commit data/ 回 repo         ────────▶ 讀最新快照
```

## 本機開發

```bash
python3 -m venv .venv
./.venv/bin/pip install -r requirements.txt
./.venv/bin/python main.py            # 跑一輪（未設 Telegram 則只印預覽）
./.venv/bin/python -m pytest -q       # 跑測試（需另裝 pytest）
```

產物：`data/snapshots/<時間戳>.json`（每輪）與 `data/latest.json`（最新狀態，供網頁讀）。

## 部署設定

1. **建立 repo**（建議 private）並推上本專案。
2. **Telegram Bot**：向 [@BotFather](https://t.me/BotFather) 建立 bot 取得 token；
   對 bot 送一則訊息後，用 `https://api.telegram.org/bot<token>/getUpdates` 取得你的 chat id。
3. **設定 Secrets**（repo → Settings → Secrets and variables → Actions）：
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`
4. **允許 Actions 寫入**：Settings → Actions → General → Workflow permissions →
   選「Read and write permissions」（workflow 已宣告 `contents: write`）。
5. **啟用 Pages**：Settings → Pages → Source 選 `main` 分支，即可用網頁。
6. 排程會每 3 小時自動跑；也可在 Actions 頁面按「Run workflow」手動觸發。

## 已知限制

- 列表頁為 JS 動態渲染，純 HTTP 只拿得到 SSR 首頁；用多排序聯集法湊，實測單一訂閱可湊到 ~34 筆。
  若實際物件更多需改用 Playwright（後續）。
- 相對刊登時間換算為絕對日期，誤差約一天內。
- 同社區多仲介重複刊登尚未去重（後續）。
- 591 可能封鎖機房 IP；若 Actions 被擋，可改用自架 runner 跑本機。
