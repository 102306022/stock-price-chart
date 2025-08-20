import os
import json
import time
import math
import pandas as pd
import mplfinance as mpf
from datetime import datetime, timedelta
from fugle_marketdata import RestClient


# ====== 可調參數 ======
SYMBOLS = ["2330", "2317", "0050"] # 實際要抓的清單：改這裡
DAYS_BACK = 180 # 往回抓幾天（日K）
MAV = (20, 60) # 移動均線
OUT_DIR = "charts"
TIMEFRAME = "D" # D/W/M；如需分K請改為 '1','5' 等
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
print(f"[{symbol}] 失敗：{e}")
