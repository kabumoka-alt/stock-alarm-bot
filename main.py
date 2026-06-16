import os
import requests
import pandas as pd
from ta.momentum import RSIIndicator
import time

TOKEN = os.environ.get("TELEGRAM_TOKEN")
CHAT_ID = os.environ.get("CHAT_ID")
FINNHUB_KEY = os.environ.get("FINNHUB_KEY")

def send(msg):
    requests.get(
        f"https://api.telegram.org/bot{TOKEN}/sendMessage",
        params={"chat_id": CHAT_ID, "text": msg}
    )

# 📊 상승률 TOP 100 가져오기
def get_top_gainers():
    url = f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={FINNHUB_KEY}"
    data = requests.get(url).json()

    # 실제 가격/변동률 가져오기
    symbols = [d["symbol"] for d in data[:200]]  # 과부하 방지

    movers = []

    for s in symbols:
        q = requests.get(
            f"https://finnhub.io/api/v1/quote?symbol={s}&token={FINNHUB_KEY}"
        ).json()

        if "c" not in q:
            continue

        change = ((q["c"] - q["pc"]) / q["pc"]) * 100
        movers.append((s, change, q["c"], q["pc"]))

    movers.sort(key=lambda x: x[1], reverse=True)

    return movers[:100]  # TOP 100

def get_rsi(symbol):
    url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=15&count=100&token={FINNHUB_KEY}"
    data = requests.get(url).json()

    if "c" not in data:
        return None

    close = pd.Series(data["c"])
    return RSIIndicator(close).rsi().iloc[-1]

while True:
    try:
        top = get_top_gainers()

        for s, change, price, prev in top:

            if change < 30:
                continue

            rsi = get_rsi(s)

            if rsi and 50 <= rsi <= 70:
                send(f"🚨 급등 TOP100\n{s}\n+{change:.2f}% RSI:{rsi:.1f}")

        time.sleep(60)

    except Exception as e:
        print(e)
        time.sleep(60)
