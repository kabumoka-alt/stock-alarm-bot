import os
import requests
import time

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_KEY = os.getenv("FINNHUB_KEY")

# 🔥 미국 대형 + 인기주 (TOP100 대신 안정 버전)
SYMBOLS = [
    "AAPL","TSLA","NVDA","AMD","META","MSFT","AMZN","GOOGL","SPY","QQQ",
    "PLTR","NFLX","INTC","SOFI","BABA","ORCL","DIS","UBER","LYFT","SNOW",
    "COIN","MSTR","RIOT","MARA","SHOP","SQ","PYPL","AMD","TSM","BA"
]

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
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_KEY}"
        r = requests.get(url).json()
        return r
    except:
        return {}

print("BOT STARTED")

while True:
    try:
        for s in SYMBOLS:

            data = get_price(s)

            current = data.get("c")
            prev = data.get("pc")

            if not current or not prev or prev == 0:
                continue

            change = ((current - prev) / prev) * 100

            print(s, change)

            # 🚀 실전 기준 (급등 알림)
            if change >= 5:
                send(f"🚀 급등 감지\n{s}\n+{change:.2f}%")

        time.sleep(60)

    except Exception as e:
        print("error:", e)
        time.sleep(10)
