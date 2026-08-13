# 591 租屋訂閱監控系統 — 部署與設定教學

本文帶你從零把這套系統部署到 **GitHub Actions（排程爬蟲）+ GitHub Pages（網頁）**，
全靜態、免費、免維運。並涵蓋 GitHub Token 權限、Telegram 通知與日常使用。

> 以本專案的實際設定為例：帳號 `YS-WEI`、repo `rent591-monitor`、
> 網頁網址 `https://YS-WEI.github.io/rent591-monitor/`。你換成自己的即可。

---

## 0. 系統怎麼運作（先看懂再部署）

```
GitHub Actions（cron 每 3 小時）              GitHub Pages（靜態網頁）
  執行 main.py                                 ui/591訂閱管理.html
   讀 subscriptions.json + watchlist.json       讀 data/latest.json 顯示狀態
   → 抓 591 → 程式端過濾 → 比對 → 通知           透過 GitHub API 讀寫訂閱/關注
   → 把快照 commit 回 repo         ───────────▶ 讀到最新資料
```

- **抓取**：由 GitHub 的伺服器定時跑，跑完把結果 `data/latest.json` 存回 repo。
- **網頁**：GitHub Pages 托管那份 HTML；顯示狀態、也能編輯訂閱/加關注（透過你的 Token 寫回 repo）。
- **兩者唯一接點是 repo 裡的檔案**，沒有需要保活的伺服器。

---

## 1. 前置準備

1. 一個 **GitHub 帳號**（本例 `YS-WEI`）。
2. 本機已安裝 **git**（`git --version` 可確認）。
3. 推送方式二選一：
   - **SSH 金鑰**（推薦，本專案用這個）
   - 或 GitHub 網頁直接上傳 / GitHub Desktop

### （選用）設定 SSH 金鑰別名

若你有多個 GitHub 帳號，可在 `~/.ssh/config` 加一個別名，指定用哪把金鑰：

```
Host github-personal
  HostName github.com
  AddKeysToAgent yes
  UseKeychain yes
  IdentityFile ~/.ssh/id_shaun
  IdentitiesOnly yes
```

測試連線（會回 `Hi <你的帳號>!` 代表成功）：

```bash
ssh -T git@github-personal
```

之後推送用 `git@github-personal:<帳號>/<repo>.git` 這種網址，就會走這把金鑰。

---

## 2. 建立 GitHub Repo（建議 Public）

到 <https://github.com/new> 建立：

- **Repository name**：`rent591-monitor`
- **選 Public** ✅（重要原因見下）
- **不要**勾 Add README / .gitignore / license（留空，避免推送衝突）
- 按 **Create repository**

### 為什麼建議 Public？

| | Public | Private（免費方案） |
|---|---|---|
| GitHub Pages | ✅ 可用 | ❌ 免費方案私有 repo **不能開 Pages**（需付費 Pro） |
| Actions 分鐘 | 無限 | 2000 分/月 |

免費方案下，**要用網頁就必須 Public**。公開的只有「搜尋條件」與「591 快照」這類不敏感資料；
**Telegram Token 與 GitHub Token 都不會進 repo**（分別在 Secrets 與你的瀏覽器），即使 Public 也安全。

---

## 3. 推送程式碼

在專案資料夾內：

```bash
git init
git branch -M main
git add -A
git commit -m "feat: 591 租屋訂閱監控系統"

# 設定遠端（用 SSH 別名）
git remote add origin git@github-personal:YS-WEI/rent591-monitor.git
git push -u origin main
```

> 若不用 SSH，遠端改成 `https://github.com/YS-WEI/rent591-monitor.git`，
> 推送時依提示登入即可。

推完到 GitHub repo 頁面應該能看到所有檔案。

---

## 4. 開啟 Actions 寫入權限（必要）

排程跑完要把快照 commit 回 repo，需要寫入權限：

**Repo → Settings → Actions → General → 最下方 Workflow permissions
→ 選「Read and write permissions」→ Save**

（workflow 檔 `.github/workflows/monitor.yml` 已宣告 `contents: write`，這個設定是雙保險。）

---

## 5. 啟用 GitHub Pages（要網頁才需要）

**Repo → Settings → Pages → Source 選「Deploy from a branch」
→ Branch 選 `main`、資料夾 `/(root)` → Save**

等 1～2 分鐘後，網址會是：**`https://YS-WEI.github.io/rent591-monitor/`**
（會自動導向 `ui/591訂閱管理.html`）

---

## 6. 手動觸發第一輪，確認能跑

**Repo → Actions 分頁 →**（若提示啟用就按 **Enable**）**→ 左側「591 監控排程」
→ 右上 Run workflow → Run**

跑完後：
- Actions 該次 run 應為 ✅ 綠燈。
- repo 的 commit 紀錄會出現一筆 `github-actions[bot]` 的「更新快照」。
- 打開網頁就能看到抓到的物件。

> ⚠️ 若看到 `Node.js 20 is deprecated…` 那是**警告不是錯誤**，可忽略。
> 偶爾第一個請求 403、重試後成功也是正常（591 對機房 IP 偶發反爬，程式會自動重試）。

---

## 7. 建立 GitHub Token（讓網頁能編輯訂閱 / 加關注 / 立即更新）

網頁要「一鍵寫回 repo」與「立即更新」，需要一組 **fine-grained token**。

**Repo 或帳號 → Settings → 左下 Developer settings → Personal access tokens
→ Fine-grained tokens → Generate new token**

填寫：

| 欄位 | 值 |
|---|---|
| Token name | `rent591-ui`（隨意） |
| Expiration | 自訂（如 90 天，到期再重簽） |
| Resource owner | 你的帳號（`YS-WEI`） |
| Repository access | **Only select repositories → 勾 `rent591-monitor`** |

### 設定權限（重點，UI 容易卡在這）

權限不是預先列好的，要**自己加**：

1. 在 **Permissions → Repository permissions** 按 **`+ Add permissions`**。
2. 在跳出的清單裡**勾選 `Contents`**（這一步只選項目，**沒有讀寫選項是正常的**）。
3. 再勾選 **`Actions`**（給「立即更新」用）。
4. 關掉清單後，表格會多出 `Contents`、`Actions` 兩列，**各自右邊有個 Access 下拉**
   （預設 `Read-only`）→ **都改成 `Read and write`**。
5. `Metadata — Read-only` 會自動附帶，正常，不用動。

最終權限應為：

- **Contents：Read and write**（讀寫 subscriptions.json / watchlist.json）
- **Actions：Read and write**（用「立即更新」觸發排程）
- Metadata：Read-only（自動）

按 **Generate token**，**複製那串 `github_pat_...`（只顯示這一次！）**。

> 只需要編輯訂閱/關注、不需要「立即更新」的話，Actions 權限可省略，只給 Contents 即可。

---

## 8. 在網頁填入 Token

打開 `https://YS-WEI.github.io/rent591-monitor/` → 右上 **⚙️ 設定**，填：

- owner：`YS-WEI`
- repo：`rent591-monitor`
- branch：`main`
- token：貼上剛才的 `github_pat_...`

按 **儲存並連線**。頂端會顯示「已連線 · 最新更新 …」，狀態頁出現物件。

> Token 只存在**你這台瀏覽器的 localStorage**，不會寫進 repo，也不會外流。
> 換裝置要重貼；Token 到期後在 GitHub 重簽再貼即可（可直接 Edit 現有 token 續期，token 字串不變）。

---

## 9.（選用）Telegram 通知

不設也沒關係，只是不推播、流程照跑。要的話：

1. 在 Telegram 找 **@BotFather** → `/newbot` → 取得 **bot token**。
2. 對你的新 bot 傳一則訊息，然後打開
   `https://api.telegram.org/bot<你的token>/getUpdates`，
   在回應裡找 `chat.id`（那串數字就是你的 **chat id**）。
3. 回 GitHub：**Repo → Settings → Secrets and variables → Actions → New repository secret**，
   新增兩個：
   - `TELEGRAM_BOT_TOKEN`
   - `TELEGRAM_CHAT_ID`

之後每輪若有新增/降價/下架，就會推到你的 Telegram（依區域分組）。

> Token 放在 Secrets（加密），即使 repo 是 Public 也讀不到。

---

## 10. 日常使用

- **狀態頁**：看本輪的 🆕 新增 / 💰 降價 / ❌ 下架 與全部在架；
  頂端「只看區域」下拉可只看某一區；卡片有封面圖、格局、坪數、管理費、車位、更新時間。
- **訂閱頁**：新增/編輯/暫停/刪除訂閱。區域用下拉選→加標籤（可複選）。存檔即 commit 回 repo。
- **關注頁**：在狀態頁點物件的 ☆ 加入關注；關注頁也有「只看區域」下拉。
- **🔄 立即更新**：不想等排程，按了會觸發一輪，約 1～2 分鐘後自動刷新（需 Token 有 Actions 權限）。

### 自動更新時間（台灣時間）

每 3 小時整點：**02:00 / 05:00 / 08:00 / 11:00 / 14:00 / 17:00 / 20:00 / 23:00**
（GitHub 排程可能延遲數分鐘，屬正常）

**改頻率**：編輯 `.github/workflows/monitor.yml` 的 cron（UTC 時間）：
- 每 2 小時：`0 */2 * * *`
- 每 6 小時：`0 */6 * * *`

---

## 11. 常見問題 / 排錯

| 症狀 | 原因 / 解法 |
|---|---|
| 網頁改了沒變 | GitHub Pages 要 1～2 分鐘重建；瀏覽器強制重載 **Cmd+Shift+R**，或用無痕視窗 |
| 打開網頁要我填設定 | 尚未在 ⚙️ 設定填 owner/repo/token（Public repo 只看狀態也需先填一次連線） |
| 立即更新跳「缺 Actions 權限」 | Token 沒給 **Actions: Read and write**，去 Edit token 補上 |
| Actions 紅燈、抓到 0 筆 | 591 偶發擋機房 IP；程式有「保險絲」會中止該輪不污染資料，下一輪通常自動恢復 |
| 某區數量比 591 少一點 | 純 HTTP 只抓得到每區「最新那批」；差幾筆屬正常。要完全一致需改用 Playwright（重解法） |
| 改了訂閱沒馬上生效 | 排程要下一輪才套用；想即時就按「🔄 立即更新」 |
| `Node.js 20 is deprecated` | 只是警告，不影響執行，忽略即可 |
| 圖片沒顯示 | 可能是 591 對外站防盜連；多數情況正常 |
| Token 到期 | 到 Fine-grained tokens 頁 Edit 續期（token 字串不變，網頁不用重貼） |

---

## 12. 安全須知

- **GitHub Token**：用 fine-grained、只授權這個 repo 的 Contents/Actions，只存瀏覽器，可隨時在 GitHub 撤銷。
- **Telegram Token**：只放在 Actions Secrets，永遠不要寫進程式或 repo。
- repo 公開的只有搜尋條件與 591 公開物件資料，金鑰類完全不在 repo 內。

---

完成以上，系統就會 24 小時自動幫你監控 591，並在網頁與 Telegram 呈現變化。
