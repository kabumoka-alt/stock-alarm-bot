import os
import requests
import time
from datetime import datetime, timezone

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_KEY = os.getenv("FINNHUB_KEY")


# -----------------------------
# ⛔ 미국장 시간 체크 (UTC)
# -----------------------------
def is_market_open():
    now = datetime.now(timezone.utc)
    hour = now.hour
    minute = now.minute

    # 13:30 ~ 20:00 UTC
    if hour < 13 or hour > 20:
        return False
    if hour == 13 and minute < 30:
        return False
    if hour == 20 and minute > 0:
        return False

    return True


# -----------------------------
# 📩 텔레그램 전송
# -----------------------------
def send(msg):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": msg}
        )
    except:
        pass


# -----------------------------
# 📊 종목 리스트
# -----------------------------
def get_symbols():
    url = f"https://finnhub.io/api/v1/stock/symbol?exchange=US&token={FINNHUB_KEY}"
    r = requests.get(url, timeout=10).json()

    if not isinstance(r, list):
        return []

    return [x["symbol"] for x in r[:200]]  # 속도 제한


# -----------------------------
# 📈 가격 + 등락률
# -----------------------------
def get_price_change(symbol):
    try:
        url = f"https://finnhub.io/api/v1/quote?symbol={symbol}&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=5).json()

        price = r.get("c")
        prev = r.get("pc")

        if not price or not prev or prev == 0:
            return None

        change = ((price - prev) / prev) * 100

        return price, change

    except:
        return None


# -----------------------------
# 📊 거래량 비율
# -----------------------------
def get_volume_ratio(symbol):
    try:
        url = f"https://finnhub.io/api/v1/stock/candle?symbol={symbol}&resolution=5&count=20&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=5).json()

        volumes = r.get("v", [])
        if len(volumes) < 5:
            return None

        avg = sum(volumes[:-1]) / len(volumes[:-1])
        last = volumes[-1]

        if avg == 0:
            return 0

        return last / avg

    except:
        return None


# -----------------------------
# 🔥 RSI
# -----------------------------
def get_rsi(symbol):
    try:
        url = f"https://finnhub.io/api/v1/indicator?symbol={symbol}&resolution=5&indicator=rsi&timeperiod=14&token={FINNHUB_KEY}"
        r = requests.get(url, timeout=5).json()

        values = r.get("rsi", [])
        if not values:
            return None

        return values[-1]

    except:
        return None


# -----------------------------
# 🚀 10분 급등 확률 모델
# -----------------------------
def predict_10min_pump(change, volume_ratio, rsi):
    score = 0

    # 📈 초기 상승
    if 1 <= change <= 3:
        score += 30
    elif 3 < change <= 6:
        score += 20

    # 💣 거래량
    if volume_ratio >= 4:
        score += 30
    elif volume_ratio >= 3:
        score += 25
    elif volume_ratio >= 2:
        score += 15

    # 🔥 RSI
    if 50 <= rsi <= 60:
        score += 25
    elif 60 < rsi <= 70:
        score += 20
    elif 70 < rsi <= 80:
        score += 5
    else:
        score -= 10

    # ⚠️ 과열 패널티
    if change > 8:
        score -= 30

    return max(0, min(score, 100))


# -----------------------------
# 🚀 실행 시작
# -----------------------------
print("🚀 10MIN PUMP SCANNER STARTED")

sent = set()

while True:
    try:
        if not is_market_open():
            print("⛔ MARKET CLOSED")
            time.sleep(300)
            continue

        symbols = get_symbols()
        results = []

        for s in symbols:
            price_data = get_price_change(s)
            vol_ratio = get_volume_ratio(s)
            rsi = get_rsi(s)

            if not price_data or vol_ratio is None or rsi is None:
                continue

            price, change = price_data

            prob = predict_10min_pump(change, vol_ratio, rsi)

            if prob >= 75:
                results.append((s, price, change, vol_ratio, rsi, prob))

        # 🔥 확률 높은 순 정렬
        results.sort(key=lambda x: x[5], reverse=True)

        print(f"FOUND: {len(results)} candidates")

        for s, price, change, vol, rsi, prob in results[:10]:

            if s in sent:
                continue

            msg = (
                f"🚨 10분 급등 확률 HIGH\n"
                f"{s}\n"
                f"현재가: ${price:.2f}\n"
                f"등락: +{change:.2f}%\n"
                f"RSI: {rsi:.1f}\n"
                f"거래량: {vol:.2f}x\n"
                f"🔥 확률: {prob}/100"
            )

            print(msg)
            send(msg)

            sent.add(s)

        time.sleep(60)

    except Exception as e:
        print("error:", e)
        time.sleep(10)
