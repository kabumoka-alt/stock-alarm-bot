import os
import requests
import pandas as pd
from ta.momentum import RSIIndicator
import time

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")

WATCHLIST = ["AAPL", "TSLA", "NVDA", "PLTR", "AMD", "META"]

def send(msg):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

def get_price(symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token=demo"
        return requests.get(url).json()
    except:
        return {}

def get_rsi(symbol):
    try:
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=15&count=100&token=demo"
        data = requests.get(url).json()

        if "c" not in data:
            return None

        if len(data["c"]) < 2:
            return None

        close = pd.Series(data["c"])

        rsi_series = RSIIndicator(close).rsi()

        if rsi_series.empty:
            return None

        return rsi_series.iloc[-1]

    except:
        return None

while True:
    try:
        for s in WATCHLIST:

            data = get_price(s)

            current = data.get("c")
            prev = data.get("pc")

            if not current or not prev or prev == 0:
                continue

            change = ((current - prev) / prev) * 100

            rsi = get_rsi(s)

            if rsi is None:
                continue

            if change >= 30 and 50 <= rsi <= 70:
                send(f"🚨 급등\n{s}\n+{change:.2f}%\nRSI {rsi:.1f}")

        time.sleep(60)

    except Exception as e:
        print("loop error:", e)
        time.sleep(10)
