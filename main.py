import requests
import time
from datetime import datetime
import pytz
import pandas as pd

# ======================
# 🔥 설정값
# ======================
TELEGRAM_TOKEN = "YOUR_BOT_TOKEN"
CHAT_ID = "YOUR_CHAT_ID"

SYMBOLS = ["AAPL", "TSLA", "NVDA", "AMD"]  # 감시 종목

RSI_PERIOD = 14
SCAN_INTERVAL = 60  # 60초마다 체크

# ======================
# 📩 텔레그램 전송
# ======================
def send_telegram(msg):
    url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    data = {"chat_id": CHAT_ID, "text": msg}
    try:
        requests.post(url, data=data, timeout=10)
    except Exception as e:
        print("Telegram error:", e)

# ======================
# 🕒 미국장 시간 체크 (핵심 수정본)
# ======================
def is_market_open():
    ny = pytz.timezone("America/New_York")
    now = datetime.now(ny)

    # 평일 체크 (월~금)
    if now.weekday() >= 5:
        return False

    # 09:30 ~ 16:00 (미국 정규장)
    open_time = now.replace(hour=9, minute=30, second=0, microsecond=0)
    close_time = now.replace(hour=16, minute=0, second=0, microsecond=0)

    return open_time <= now <= close_time

# ======================
# 📊 RSI 계산
# ======================
def calc_rsi(prices, period=14):
    df = pd.DataFrame(prices, columns=["close"])
    delta = df["close"].diff()

    gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()

    rs = gain / loss
    rsi = 100 - (100 / (1 + rs))
    return rsi.iloc[-1]

# ======================
# 📡 가격 가져오기 (예시: Finnhub)
# ======================
def get_prices(symbol):
    url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token=YOUR_API_KEY"
    r = requests.get(url).json()

    # 간단히 close 기준 mock (실전은 candle API 추천)
    return [r["c"], r["c"], r["c"], r["c"], r["c"], r["c"], r["c"], r["c"], r["c"], r["c"],
            r["c"], r["c"], r["c"], r["c"], r["c"]]

# ======================
# 🚀 메인 스캐너
# ======================
def run():
    send_telegram("🚀 10MIN PUMP MODEL STARTED")

    while True:
        try:
            if not is_market_open():
                print("⛔ MARKET CLOSED")
                time.sleep(30)
                continue

            print("📊 SCANNING...")

            for symbol in SYMBOLS:
                prices = get_prices(symbol)
                rsi = calc_rsi(prices)

                print(symbol, "RSI:", rsi)

                # 🚨 조건 (원하면 수정 가능)
                if 50 <= rsi <= 70:
                    msg = f"🚀 {symbol} SIGNAL\nRSI: {rsi:.2f}"
                    send_telegram(msg)

            time.sleep(SCAN_INTERVAL)

        except Exception as e:
            print("ERROR:", e)
            time.sleep(10)

# ======================
# ▶ 실행
# ======================
if __name__ == "__main__":
    run()
