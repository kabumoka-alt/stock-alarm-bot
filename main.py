import os
import requests
import time
import pandas as pd
from ta.momentum import RSIIndicator

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_KEY = os.getenv("FINNHUB_KEY")

WATCHLIST = []

def send(msg):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass

def get_symbols():
    url = f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={FINNHUB_KEY}"
    r = requests.get(url).json()
    if not isinstance(r, list):
        return []
    return [x["symbol"] for x in r[:200]]

def get_change(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_KEY}"
    q = requests.get(url).json()

    c = q.get("c")
    pc = q.get("pc")

    if not c or not pc or pc == 0:
        return None

    return ((c - pc) / pc) * 100, c

def get_rsi(symbol):
    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=15&count=50&token={FINNHUB_KEY}"
    d = requests.get(url).json()

    if "c" not in d or len(d["c"]) < 10:
        return None

    close = pd.Series(d["c"])
    rsi = RSIIndicator(close).rsi()

    if rsi.empty:
        return None

    return rsi.iloc[-1]

print("BOT STARTED")

while True:
    try:
        symbols = get_symbols()

        for s in symbols:
            res = get_change(s)
            if not res:
                continue

            change, price = res

            if change < 20:
                continue

            rsi = get_rsi(s)
            if rsi is None:
                continue

            if change >= 30 and 50 <= rsi <= 70:
                send(f"🚨 TOP100 급등\n{s}\n+{change:.2f}%\nRSI {rsi:.1f}")

        time.sleep(60)

    except:
        time.sleep(10)
