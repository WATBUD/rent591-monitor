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

## 13. 別人 Fork 這個專案後怎麼設定

Fork 會複製整個 repo（含程式碼與**原作者的資料**）。因為 Fork 有幾個和「從零建立」不同的地方，
照這個順序做：

### 13-1. Fork

到原 repo 頁面，右上角按 **Fork** → 建立 `你的帳號/rent591-monitor`。
（建議維持 **Public**，理由同 §2：免費方案私有 repo 不能開 Pages。）

### 13-2. 啟用 Actions（Fork 預設是關閉的！）

Fork 出來的 repo **Actions 預設停用**，一定要手動開：

**你的 repo → Actions 分頁 → 點「I understand my workflows, go ahead and enable them」**

### 13-3. 開 Actions 寫入權限

同 §4：**Settings → Actions → General → Workflow permissions → Read and write → Save**

### 13-4. 換成你自己的資料（清掉原作者的）

Fork 會帶著原作者的訂閱與快照，換成你自己的：

1. **訂閱條件**：編輯 `subscriptions.json`（GitHub 網頁直接改，或部署好後用網頁介面改），
   把 `subscriptions` 換成你要的城市/區域/租金等條件。
2. **清關注清單**：把 `watchlist.json` 內容改成 `{"items": {}}`。
3.（選用）**清舊快照**：刪掉 `data/snapshots/` 裡的舊檔與 `data/latest.json`；
   第一次跑排程會自動重建成你自己的資料。

> 這些檔案都可以直接在 GitHub 網頁上編輯/刪除（進檔案 → 鉛筆或垃圾桶圖示）。

### 13-5. 啟用 Pages

同 §5：**Settings → Pages → Deploy from a branch → main / (root)**。
你的網址會變成 **`https://你的帳號.github.io/rent591-monitor/`**。

### 13-6. 建立你自己的 Token

同 §7，但 **Resource owner 選你自己、Repository 選你 Fork 出來的 repo**。
權限一樣：**Contents: Read and write**（+ 要用立即更新再加 **Actions: Read and write**）。

### 13-7. 網頁填你自己的設定

打開你的 Pages 網址 → ⚙️ 設定，**owner 填你自己的帳號**、repo 填 `rent591-monitor`、
branch `main`、貼上你的 Token → 儲存並連線。

### 13-8. （選用）你自己的 Telegram

同 §9，在**你的 repo** 的 Secrets 加 `TELEGRAM_BOT_TOKEN`、`TELEGRAM_CHAT_ID`。
（原作者的 Secrets 不會被 Fork 帶過來，本來就要自己設。）

### 13-9. 手動觸發第一輪

同 §6：Actions → Run workflow → Run，確認綠燈且 bot 有 commit 新快照。

### Fork 常見問題

| 症狀 | 解法 |
|---|---|
| 排程都沒跑 | Fork 的 Actions 預設停用，要先做 §13-2 啟用 |
| 網頁顯示的是別人的物件 | 還沒做 §13-4 換資料；改 `subscriptions.json` 後跑一輪即更新 |
| 「立即更新」沒反應 | owner 要填**你自己**、Token 要有 Actions 權限 |
| 排程一段時間後自己停了 | GitHub 會停用「長期無活動」repo 的排程；每輪 commit 快照即算活動可自我維持，手動 Run 一次也會重新啟用 |

---

## 14. 調整更新頻率

更新頻率由 `.github/workflows/monitor.yml` 裡的 **cron** 決定，**目前無法從網頁改**，
要編輯這個檔（最簡單是用 GitHub 網頁編輯器）。

### 怎麼改

1. 你的 repo → 進 `.github/workflows/monitor.yml`。
2. 按右上角**鉛筆圖示**編輯。
3. 找到這一行，改掉 cron 字串：
   ```yaml
   schedule:
     - cron: "0 */3 * * *"   # 預設每 3 小時
   ```
4. 按 **Commit changes** 存檔。下一次就照新頻率跑。

### ⚠️ cron 用的是 UTC（比台灣時間慢 8 小時）

`*/N` 這種「每 N 小時」不受時區影響，直接用即可；但若要指定「幾點跑」，
記得**台灣時間 = UTC + 8**（例：想台灣 09:00 跑 → 寫 UTC `1`）。

### 常用範例

| 需求 | cron 寫法 |
|---|---|
| 每 2 小時 | `0 */2 * * *` |
| 每 3 小時（預設） | `0 */3 * * *` |
| 每 6 小時 | `0 */6 * * *` |
| 每 12 小時 | `0 */12 * * *` |
| 每天一次（台灣 09:00） | `0 1 * * *` |
| 每天兩次（台灣 09:00、21:00） | `0 1,13 * * *` |

也可以列多行 cron 指定多個時段，例如：
```yaml
schedule:
  - cron: "0 1 * * *"    # 台灣 09:00
  - cron: "0 13 * * *"   # 台灣 21:00
```

### 注意事項

- **不要設太頻繁**（如每幾分鐘）：會增加 591 擋機房 IP 的機率，也沒必要；租屋監控每 2～6 小時很夠。
- GitHub 的排程本來就**常延遲數分鐘**，不保證分秒準時。
- 不想等排程時，隨時可用網頁的 **🔄 立即更新** 或 Actions 頁的 **Run workflow** 手動跑一輪。

> （進階）若想「在網頁上用下拉選頻率」，技術上可行，但你的 token 需再加 **Workflows: Read and write**
> 權限（GitHub 規定改 workflow 檔需要此權限）。目前版本走「編輯 monitor.yml」這個較單純的方式。

---

完成以上，系統就會 24 小時自動幫你監控 591，並在網頁與 Telegram 呈現變化。
