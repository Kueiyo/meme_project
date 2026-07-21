# Meme Coin On-Chain Forensics Toolkit
### 迷因幣鏈上籌碼結構與 First Funder 資金溯源分析工具

> 2026 鏈上數據讀書會・實戰研究專案

## 專案簡介

本專案鎖定 Solana 鏈上的熱門 Meme 幣，透過 Helius RPC / API 自動化追蹤 **Top 50 大戶**的鏈上足跡，回答三個研究問題：

1. **籌碼健不健康？** — Top 50 集中度、錢包關聯度（群聚係數）、早鳥比例、CEX 錢包數。
2. **大戶的第一桶金從哪來？** — 逆向溯源每個大戶最早收到資金的來源地址（First Funder），藉此分辨「莊家老鼠倉矩陣」還是「社群共識大幣」。
3. **開盤瞬間是誰在買？** — 鎖定代幣的創世區塊，比對開盤秒買的錢包是否至今仍盤踞 Top 50。

三個問題各自對應一條獨立的資料處理管線（見下方「系統架構」），共用同一組 `1_data_raw → 2_data_processed → 3/4/5_reports_*` 的資料夾骨架。

---

## 系統架構總覽

| # | 管線 | 進入點 | 核心腳本 | 用途 |
|---|------|--------|----------|------|
| A | **鏈上籌碼結構分析** | `main.py` | `step1_fetch_top50.py` → `step2_calc_metrics.py` → `step3_generate_report.py` → `step4_event_analysis.py` | 算出單一代幣的四大指標（集中度／群聚係數／早鳥比例／CEX 數），產出文字報告、靜態圖、互動網路圖 |
| B | **First Funder 資金溯源引擎** | `batch_funder_engine_v2.py`（新版，建議使用）<br>`batch_funder_engine_v1.py`（舊版，僅供對照） | 見下方「新舊版本比較」 | 批次回溯 Top 50 大戶的「第一桶金」來源，計算資金聚集度、抓出私人莊家地址 |
| C | **創世狙擊系統** | `sniper_engine.py` | — | 直接掃描代幣開盤後的前幾個區塊，抓出「開盤秒買、現在還在 Top 50」的老鼠倉錢包 |

管線 A 和 B 都需要 `1_data_raw/top50_{COIN}.json`（由 Step 1 產生）作為輸入；B 額外需要 `master_sheet.csv`（讀書會 Google Sheet 匯出的總表）來取得 KOL 發文時間，作為 T=0 錨點。

---

## 環境設置

```bash
# 1. 安裝相依套件（已鎖定 aiohttp / pandas / matplotlib / networkx / pyvis / python-dotenv 等版本）
uv sync

# 2. 設定 API Key：複製範例檔並填入你自己的 Helius API Key
cp .env.example .env
# 編輯 .env → HELIUS_API_KEY=你的金鑰
```

> ⚠️ **資安提醒**：舊版 `config.py` 曾將 API Key 以明碼寫死在原始碼中。現在已改為從 `.env` 讀取（`.env` 已加入 `.gitignore`，不會被提交到版控），請勿把金鑰貼回程式碼或推上任何公開倉庫。

`main.py` 執行時會自動建立 `1_data_raw` ~ `5_reports_html` 五個資料夾；其餘腳本（`batch_funder_engine_*.py`、`sniper_engine.py` 等）需要在 `my_project/` 根目錄下執行，因為程式內部使用相對路徑讀寫檔案。

---

## Pipeline A：鏈上籌碼結構分析（main.py）

```bash
uv run python main.py
```

流程讀取 `kind.txt`（格式：`代幣代號,合約地址[,KOL發文時間]`），逐一執行：

| 步驟 | 腳本 | 產出 |
|------|------|------|
| Step 1 | `step1_fetch_top50.py` | `1_data_raw/top50_{COIN}.json`：Top 50 持倉地址、餘額、集中度 |
| Step 2 | `step2_calc_metrics.py` | `2_data_processed/metrics_{COIN}.json`：群聚係數、早鳥比例、CEX 錢包數；並輸出 `4_reports_img/graph_{COIN}.png`（靜態關聯圖）與 `5_reports_html/graph_{COIN}.html`（互動網路圖） |
| Step 3 | `step3_generate_report.py` | `3_reports_txt/report_{COIN}.txt`（文字報告）、`4_reports_img/dashboard_{COIN}.png`（指標儀表板） |
| Step 4（預設關閉） | `step4_event_analysis.py` | `2_data_processed/event_report_{COIN}.json`：KOL 發文前後 ±N 分鐘內活躍的 Top 50 大戶名單 |

執行開關與行為（`main.py` 檔頭的「系統執行總開關」區塊）：

- `RUN_STEP_1~4`：個別開關各步驟。
- `START_FROM_COIN`：從 `kind.txt` 中指定代幣開始跑（方便中斷後續跑）。
- `FORCE_OVERWRITE`：`True` 時即使 `metrics_{COIN}.json` 已存在也會重跑；`False` 則整個代幣跳過（斷點續傳）。
- Step 1/2 內建**本地快取**（`cache_tx_*.json`、`cache_early_*.json`），重跑不會重複打 API。

---

## Pipeline B：First Funder 資金溯源引擎（核心研究工具）

### 抓取邏輯

1. **T=0 時間基準點解析**：讀取 `master_sheet.csv` 總表，抓出同一代幣區塊內所有 KOL 推文時間，用自建的中英文日期解析器轉成 UNIX Timestamp，取「最早一篇」作為該代幣的創世建倉錨點。
2. **逆向分頁檢索**：對 Top 50 每個地址呼叫 `getSignaturesForAddress`，從最新一筆往回翻頁，每次 1000 筆，`MAX_TX_LIMIT = 3000` 做深度煞車。
3. **時間窗格過濾**：在翻到的簽名清單中，篩掉晚於 T=0（+7 天緩衝）的交易雜訊，鎖定最貼近建倉當下的那一筆。
4. **抓 First Funder**：對鎖定的簽名呼叫 `getTransaction`，取 `accountKeys` 中 `signer: true` 的帳戶，視為當初支付 Gas / 發放建倉 SOL 的來源地址。
5. **併發與防禦**：`asyncio` + `aiohttp`，`Semaphore(15)` 控制併發；指數退避 + Jitter 處理 HTTP 429；比對內建 CEX 錢包字典，區分「交易所提幣」與「私人錢包分發」。

### 新舊版本比較

| | `batch_funder_engine_v1.py`（舊版／基準版） | `batch_funder_engine_v2.py`（新版／建議使用） |
|---|---|---|
| T=0 錨定 | ❌ 沒有讀取 KOL 發文時間，直接把「翻到底的最舊一筆」當作建倉交易 | ✅ 解析 `master_sheet.csv`，用最早的 KOL 推文時間作為 T=0，過濾掉發文後的日常轉帳雜訊 |
| CSV 容錯 | 不適用 | ✅ 自動處理多行區塊、空值（`nan`）、「Jun 22, 2024」與「2024年10月23日」等中英混合日期格式 |
| CEX 字典 | 6 個地址（僅六大交易所官方熱錢包） | 11 個地址（額外收錄從歷史資料中反查出的跨幣種熱錢包 / 造市商） |
| 輸出資料夾 | `2_data_processed/batch_funder_engine/` | `2_data_processed/batch_funder_engine_v2/`（含 `anchor_timestamp` 欄位） |
| 適用情境 | 僅供與 v2 結果比對差異，或回溯舊資料 | **正式分析請一律使用這個版本** |

> 為什麼要留舊版？因為它揭示了一個真實的資料陷阱：不做 T=0 錨定，很容易把「大戶開盤半年後的日常轉帳」誤判成「當初建倉的資金來源」，導致誤判為分散持有。README 最上方保留這行對照，就是提醒未來的自己：**永遠用 v2**。

### 執行步驟

```bash
# Step 1：執行溯源引擎（抓取鏈上數據，寫入 2_data_processed/batch_funder_engine_v2/）
uv run python batch_funder_engine_v2.py

# Step 2：彙整成報表（讀取 v2 引擎結果，計算資金聚集度）
uv run python generate_report_v2.py
# → 產出 3_reports_txt/first_funder_analysis/final_funder_report_v2.csv

# Step 3（選用）：套用 master_sheet.csv 手填欄位，輸出讀書會報告用純文字檔
uv run python export_txt_report.py
# → 產出 2_data_processed/batch_funder_engine_v2/讀書會報告_核心指標.txt

# Step 4（選用）：把 final_funder_report_v2.csv 轉成視覺化儀表板 / 互動網頁
uv run python generate_v2_dashboards.py     # → 3_reports_txt & 4_reports_img/funder_tracker_dashboards/
uv run python generate_v2_html_reports.py   # → 5_reports_html/funder_tracker_dashboards/

# Step 5（選用）：把 First Funder → 受控大戶的關聯，畫成互動蜘蛛網圖
uv run python generate_v2_spider_web.py     # → 5_reports_html/v2_spider_graphs/
```

`generate_v2_spider_web.py` 直接讀取 `batch_funder_engine_v2.py` 的原始 JSON（不經過 CSV），用 `networkx` 把每個 First Funder 地址當中心節點、其控制的大戶錢包當子節點展開成星狀圖，再交給 `pyvis` 輸出成可拖拉縮放的深色互動網頁（`spider_{COIN}.html`）；節點大小依關聯大戶數（degree）縮放，滑鼠懸停可看完整地址。第一次執行 `pyvis` 會在專案根目錄產生 `lib/`（vis-network / tom-select 等前端靜態資源），供產出的 HTML 離線讀取，屬自動產生的執行期資源，可視需求加入 `.gitignore`。

舊版指令（僅供對照差異，不建議用於正式分析）：

```bash
uv run python batch_funder_engine_v1.py   # 寫入 2_data_processed/batch_funder_engine/
uv run python generate_report.py          # 讀取上面的舊資料夾，輸出 3_reports_txt/first_funder_analysis/funder_report_summary.csv
```

兩版引擎都內建**斷點續傳**：只要 `2_data_processed/batch_funder_engine*/{COIN}_funder.json` 已存在，重跑會直接跳過該代幣。要重新抓取，先手動刪除對應 JSON 檔。

---

## Pipeline C：創世狙擊系統（sniper_engine.py）

```bash
uv run python sniper_engine.py
```

讀取 `kind_sniper.txt`（格式：`代幣代號,合約地址,創世區塊編號`），從指定區塊開始，以 50 區塊為一批併發掃描，收集開盤後買進代幣的錢包，直到湊滿 1000 個真實買家或掃到 5000 區塊為止（安全煞車）。最後比對這批「開盤秒買」錢包與 Top 50 名單的交集，找出**從第一秒就持有到現在**的可疑老鼠倉錢包。

結果輸出至 `2_data_processed/sniper_results/sniper_result_{COIN}.json`。`kind_sniper.txt` 中創世區塊填 `???` 或 `0` 的代幣會自動跳過。

---

## 完整目錄結構

```
my_project/
├── .env                              # API Key（本機專用，已加入 .gitignore）
├── .env.example                      # API Key 範本
├── config.py                         # 從 .env 讀取 HELIUS_API_KEY
├── master_sheet.csv                  # 讀書會 Master Data 總表匯出檔（含 KOL 發文時間等人工填寫欄位）
├── kind.txt                          # Pipeline A/B 用：代幣代號,合約地址[,KOL發文時間]
├── kind_sniper.txt                   # Pipeline C 用：代幣代號,合約地址,創世區塊編號
│
├── main.py                           # Pipeline A 總控
├── step1_fetch_top50.py              # A-Step1：抓 Top 50 持有人
├── step2_calc_metrics.py             # A-Step2：群聚係數、早鳥比例、關聯圖
├── step3_generate_report.py          # A-Step3：文字報告 + 儀表板圖
├── step4_event_analysis.py           # A-Step4（選用）：KOL 事件窗口分析
│
├── batch_funder_engine_v1.py         # B：First Funder 引擎（舊版，無 T=0 錨定）
├── batch_funder_engine_v2.py         # B：First Funder 引擎（新版，建議使用）
├── generate_report.py                # B：舊版結果彙整報表
├── generate_report_v2.py             # B：新版結果彙整報表（含資金聚集度計算）
├── export_txt_report.py              # B：輸出讀書會用純文字彙整報告
├── generate_v2_dashboards.py         # B：final_funder_report_v2.csv → 圖像儀表板
├── generate_v2_html_reports.py       # B：final_funder_report_v2.csv → 互動 HTML 儀表板
├── generate_v2_spider_web.py         # B：v2 JSON → First Funder 關聯蜘蛛網（互動 HTML）
│
├── sniper_engine.py                  # Pipeline C：創世區塊狙擊系統
│
├── 1_data_raw/                       # 原始資料 + API 快取
│   ├── top50_{COIN}.json             # Top 50 持有人清單（A-Step1 產出，B/C 共用）
│   ├── cache_tx_{COIN}.json          # A-Step2 交易快取
│   └── cache_early_{COIN}.json       # A-Step2 早鳥交易快取
│
├── 2_data_processed/
│   ├── metrics_{COIN}.json           # A 的四大指標
│   ├── batch_funder_engine/          # B 舊版逐幣溯源結果
│   ├── batch_funder_engine_v2/       # B 新版逐幣溯源結果（含 anchor_timestamp）
│   └── sniper_results/               # C 的狙擊結果
│
├── 3_reports_txt/
│   ├── report_{COIN}.txt             # A 的文字報告
│   ├── first_funder_analysis/        # B 彙整 CSV（funder_report_summary.csv / final_funder_report_v2.csv）
│   └── funder_tracker_dashboards/    # B 的逐幣文字報告（generate_v2_dashboards.py 產出）
│
├── 4_reports_img/
│   ├── graph_{COIN}.png              # A 的靜態關聯圖
│   ├── dashboard_{COIN}.png          # A 的指標儀表板
│   └── funder_tracker_dashboards/    # B 的指標儀表板（避免與 A 的檔名衝突，獨立資料夾）
│
├── 5_reports_html/
│   ├── graph_{COIN}.html             # A 的互動網路圖（pyvis）
│   ├── funder_tracker_dashboards/    # B 的互動 HTML 儀表板（Chart.js）
│   └── v2_spider_graphs/             # B 的 First Funder 關聯蜘蛛網（pyvis，spider_{COIN}.html）
│
├── lib/                               # pyvis 產生的前端靜態資源（vis-network / tom-select），供 HTML 圖表離線讀取，執行期自動產生
│
└── _archive/
    ├── batch_funder_engine_v1_stale_output/   # 舊版引擎在檔名尚未修正前，一次過渡期產出的殘留資料，保留備查、目前無腳本讀寫
    └── v2_dashboards_stale_output/             # 三支 B 管線報表腳本曾一度改回舊的絕對路徑、寫回 v2_dashboards 資料夾所產出的重複資料，保留備查、目前無腳本讀寫
```

> `4_reports_img/graph_*.png` 與 `funder_tracker_dashboards/dashboard_*.png` 刻意分開存放：Pipeline A 和 Pipeline B 各自算出的「dashboard」指標定義不同（A 是鏈上原始指標，B 是資金聚集度分析），檔名撞在一起容易互相覆蓋，故拆成獨立子資料夾。

---

## 報表指標說明（供填回 Master Sheet 使用）

| 指標 | 說明 |
|------|------|
| **top50_concentration**（籌碼集中度） | Top 50 持有量 ÷ 總供給量。越高代表籌碼越集中在少數地址手中。 |
| **clustering_coefficient**（群聚係數 / 錢包關聯度） | Top 50 錢包彼此互轉的網路群聚係數（多尺度：10/50/100/500/1000 筆交易）。越高代表大戶之間互動越頻繁，可能為同一組織操作。 |
| **early_buyers_ratio**（早鳥比例） | 代幣最早期交易的參與者中，有多少比例現在仍位列 Top 50。 |
| **cex_wallet_count**（CEX 錢包數） | Top 50 中被識別為交易所熱錢包的地址數。 |
| **獨立資金源數 (Unique Funders)** | Top 50 大戶最初的資金來自多少個不同錢包。數字越小，代表籌碼源頭越集中，操盤嫌疑越高。 |
| **資金聚集度 (%)** | `最大單一私人莊家控制數 ÷ 分析大戶數 × 100`。可直接填入 Master 總表的 `clustering_coefficient` 欄位。 |
| **CEX 資金數** | 資金源自 Binance、OKX 等交易所熱錢包的大戶數量。越高代表越多獨立散戶進場。 |

---

## 已知限制與維護紀錄

- `pyproject.toml` 原本缺少 `aiohttp` / `pandas` 兩個實際有用到的套件宣告，若之前直接執行 `uv sync` 會把本機手動裝的這兩個套件移除、導致腳本壞掉；已補齊宣告並重新產生 `uv.lock`。
- `.python-version` 原標示 `3.12`，但實際可用的直譯器與 `.venv` 都是 `3.11.9`；已改為 `3.11` 並將 `requires-python` 放寬為 `>=3.11`。
- `generate_v2_dashboards.py` / `generate_v2_html_reports.py` 原本寫死 Windows 絕對路徑（`D:\生活\...`），搬動專案資料夾就會全部失效；已改為相對路徑，統一規定「所有腳本都要在 `my_project/` 根目錄下執行」。
- Master Data 總表原始檔名含空格、全形括號與 emoji（`小專案_MasterSheet_v2 - 📊 Master Data (1).csv`），已重新命名為 `master_sheet.csv`。之後若從 Google Sheet 重新匯出，記得另存/覆蓋為這個檔名再執行腳本。
- `2_data_processed/batch_funder_engine_v1/` 為過渡期產出的孤兒資料夾（沒有任何現行腳本會再讀寫），已搬到 `_archive/batch_funder_engine_v1_stale_output/`，不影響現有分析結果，僅供追溯用。
- `export_txt_report.py` / `generate_v2_dashboards.py` / `generate_v2_html_reports.py` 曾一度又回到寫死 Windows 絕對路徑、輸出到 `v2_dashboards` 資料夾的舊版寫法（與本 README 記載的行為不符），導致 `3_reports_txt`、`4_reports_img`、`5_reports_html` 底下同時存在 `v2_dashboards`（舊）與 `funder_tracker_dashboards`（新）兩份重複輸出。已重新套用相對路徑 + UTF-8 修正，舊輸出搬到 `_archive/v2_dashboards_stale_output/`。**若之後再次發現這三支腳本跑出 `v2_dashboards` 資料夾，代表又被改回舊版寫法，需要重新修正。**
- 新增 `generate_v2_spider_web.py`（First Funder 關聯蜘蛛網，pyvis 互動 HTML），原始版本同樣寫死絕對路徑，已比照其餘 B 管線腳本改為相對路徑並加上 UTF-8 guard。
