# 你要的兩種自動化做法（先給你可直接用的範本）

> 需求：每週固定取得 Fugle 網站上「特定標的」的股價圖。
>
> 解法 A（推薦）：用 **Fugle MarketData API** 抓歷史股價 → 我們自己畫 K 線圖 → 每週自動產出 PNG 檔。
>
> 解法 B：用 **Playwright 無頭瀏覽器** 開 Fugle 個股頁 → 自動截圖「股價K線」卡片 → 存 PNG。

---

## 方案比較

| 方案             | 穩定性             | 法規/權限風險            | 畫面一致性         | 自訂指標/樣式 | 維護成本  |
| -------------- | --------------- | ------------------ | ------------- | ------- | ----- |
| A. API 自製圖（推薦） | ★★★★☆           | ★★★★★（遵循 API T\&C） | ★★★☆☆（不是網站原樣） | ★★★★★   | ★★☆☆☆ |
| B. 網頁截圖        | ★★☆☆☆（DOM 變更易壞） | ★★☆☆☆（請遵守網站規範）     | ★★★★★（與網站一致）  | ★★☆☆☆   | ★★★★☆ |

> 初次建置建議走 A；若你**一定要與 Fugle 畫面一模一樣**，再補 B 當備援。

---

## A. 用 API 自動產出 K 線圖（GitHub Actions 每週跑）

### 1) 專案結構

```
.
├─ requirements.txt
├─ scripts/
│  └─ generate_charts.py
└─ .github/
   └─ workflows/
      └─ weekly.yml
```

### 2) requirements.txt

```
requests
pandas
mplfinance
fugle-marketdata
```

### 3) scripts/generate\_charts.py

```python
import os
import json
import time
import math
import pandas as pd
import mplfinance as mpf
from datetime import datetime, timedelta
from fugle_marketdata import RestClient

# ====== 可調參數 ======
SYMBOLS = ["2330", "2317", "8069"]  # 實際要抓的清單：改這裡
DAYS_BACK = 180                        # 往回抓幾天（日K）
MAV = (20, 60)                         # 移動均線
OUT_DIR = "charts"
TIMEFRAME = "D"                        # D/W/M；如需分K請改為 '1','5' 等
# ======================

API_KEY = os.environ.get("FUGLE_API_KEY")
assert API_KEY, "環境變數 FUGLE_API_KEY 未設定"

client = RestClient(api_key=API_KEY)
stock = client.stock

# 日期區間（日K有效；分K由 API 決定區間）
end_date = datetime.now().date()
start_date = end_date - timedelta(days=DAYS_BACK)

# 今天的輸出資料夾
stamp = end_date.strftime("%Y-%m-%d")
run_dir = os.path.join(OUT_DIR, stamp)
os.makedirs(run_dir, exist_ok=True)

for symbol in SYMBOLS:
    try:
        params = {"symbol": symbol, "fields": "open,high,low,close,volume"}
        if TIMEFRAME in ("D", "W", "M"):
            params.update({"from": start_date.strftime("%Y-%m-%d"),
                           "to": end_date.strftime("%Y-%m-%d"),
                           "timeframe": TIMEFRAME})
        else:
            # 分K：API 目前不支援 from/to；僅回近 30 日
            params.update({"timeframe": TIMEFRAME})

        # 用 **dict 解包** 避開 Python 關鍵字 from/to 的問題
        data = stock.historical.candles(**params)
        rows = data.get("data", [])
        if not rows:
            print(f"[{symbol}] 無資料，略過")
            continue

        df = pd.DataFrame(rows)
        # 分K會帶時間，日K/週K/月K只有日期
        df['date'] = pd.to_datetime(df['date'])
        df.set_index('date', inplace=True)
        df.rename(columns={
            'open': 'Open', 'high': 'High', 'low': 'Low', 'close': 'Close', 'volume': 'Volume'
        }, inplace=True)
        df.sort_index(inplace=True)

        # 畫圖
        save_path = os.path.join(run_dir, f"{symbol}_{TIMEFRAME}.png")
        mpf.plot(
            df,
            type='candle',
            mav=MAV,
            volume=True,
            title=f"{symbol}  {TIMEFRAME}  {start_date} ~ {end_date}",
            savefig=dict(fname=save_path, dpi=150, bbox_inches='tight')
        )
        print(f"[{symbol}] 圖檔輸出 → {save_path}")
    except Exception as e:
        print(f"[{symbol}] 失敗：{e}")
```

### 4) .github/workflows/weekly.yml（每週一 09:00 台北時間）

> GitHub Actions 的 cron 用 **UTC**，台北時間 09:00 = UTC 01:00。

```yaml
name: weekly-fugle-charts

on:
  schedule:
    - cron: "0 1 * * 1"   # 每週一 01:00 UTC（= 台北 09:00）
  workflow_dispatch:      # 允許手動觸發

jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install deps
        run: |
          python -m pip install --upgrade pip
          pip install -r requirements.txt
      - name: Generate charts
        env:
          FUGLE_API_KEY: ${{ secrets.FUGLE_API_KEY }}
        run: python scripts/generate_charts.py
      - name: Commit charts
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add charts/* || echo "no new charts"
          git commit -m "Weekly charts $(date -u +'%Y-%m-%d')" || echo "nothing to commit"
          git push || echo "nothing to push"
```

### 5) 快速啟用步驟

1. 在 GitHub 建一個空 repo，照上面結構新增三個檔案。
2. 到 **Settings → Secrets and variables → Actions → New repository secret** 新增 `FUGLE_API_KEY`。
3. 修改 `SYMBOLS`、`DAYS_BACK`、`MAV`、`TIMEFRAME`。
4. 第一次可在 Actions 頁面手動「Run workflow」；之後每週自動出圖，檔案會存到 `charts/年-月-日/`。
5. 若要自動寄信/丟 Slack，可在 workflow 後面再加一個 step（send mail / Slack webhook）。

> 備註：API 有速率限制，清單大量時建議 sleep 或分批；如需分K，API 目前固定回近 30 日。

---

## B. 用 Playwright 自動截圖 Fugle 網頁（還原網站視覺）

> 網頁結構若改動，選擇器要跟著調；建議把這個當備援或在本機先確認。

### 1) 新增檔案 scripts/snapshot\_fugle.py

```python
import os
from datetime import datetime
from playwright.sync_api import sync_playwright

SYMBOLS = ["2330", "2317", "8069"]
OUT_DIR = "snapshots"
K_CHART_SELECTOR = "section:has-text('股價K線')"  # 可能需依實際 DOM 更改
TIME_RANGE_BUTTON = "text=1Y"  # 例如點「1Y」

os.makedirs(OUT_DIR, exist_ok=True)

def snap(page, symbol):
    url = f"https://www.fugle.tw/ai/{symbol}"
    page.goto(url, wait_until="networkidle")
    # 可選：切換時間區間
    if page.locator(TIME_RANGE_BUTTON).first.is_visible():
        page.locator(TIME_RANGE_BUTTON).first.click()
    # 截圖 K 線卡片
    chart = page.locator(K_CHART_SELECTOR).first
    chart.wait_for()
    today = datetime.now().strftime("%Y-%m-%d")
    path = os.path.join(OUT_DIR, f"{today}_{symbol}.png")
    chart.screenshot(path=path)
    print(f"saved → {path}")

with sync_playwright() as p:
    browser = p.chromium.launch()
    page = browser.new_page(viewport={"width": 1440, "height": 900})
    for s in SYMBOLS:
        snap(page, s)
    browser.close()
```

### 2) workflow：.github/workflows/snapshot.yml（每週一 09:05 台北時間）

```yaml
name: weekly-fugle-snapshots

on:
  schedule:
    - cron: "5 1 * * 1"   # 09:05 TPE
  workflow_dispatch:

jobs:
  snap:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: Install Playwright
        run: |
          pip install playwright
          python -m playwright install chromium --with-deps
      - name: Run snapshot
        run: python scripts/snapshot_fugle.py
      - name: Commit images
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "41898282+github-actions[bot]@users.noreply.github.com"
          git add snapshots/* || echo "no new images"
          git commit -m "Weekly snapshots $(date -u +'%Y-%m-%d')" || echo "nothing to commit"
          git push || echo "nothing to push"
```

### 3) 選擇器小技巧

* 先本機跑 `npx playwright codegen https://www.fugle.tw/ai/2330`，實際點到「股價K線」卡片，再複製穩定的 selector。
* 有些網站會把圖放在 `canvas/svg` 內；你也可以直接鎖定 `canvas` 祖先容器。

---

## 延伸：自動寄信 / 貼 Slack

在 workflow 結尾加 Step 即可，例如：

* Email：`dawidd6/action-send-mail@v3`
* Slack：`slackapi/slack-github-action@v1`（用 Files upload API 上傳 PNG）

---

## 注意事項

* 請遵守 Fugle API 與網站使用規範；若要長期穩定、可維護，**優先使用 API**。
* 公司電腦無法裝 Python → 用 **GitHub Actions** 跑；完全不需在本機安裝。
* 想要更像「報表」：可以把多張 PNG 合併成 PDF（例如用 `img2pdf` 或 `reportlab`）。

---

### 你只要改三個地方就能用：

1. `SYMBOLS` 換成你的實際標的。
2. `DAYS_BACK` / `TIMEFRAME` 調時間尺度（一般用日K最穩）。
3. GitHub Repo 設定 `FUGLE_API_KEY` secret（方案A）。

需要我幫你把標的清單與時間週期直接嵌進去，也可以。
