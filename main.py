import os
import requests
import time
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor, as_completed

TOKEN = os.getenv("TELEGRAM_TOKEN")
CHAT_ID = os.getenv("CHAT_ID")
FINNHUB_KEY = os.getenv("FINNHUB_KEY")

SCAN_INTERVAL = 120
ALERT_COOLDOWN = 600
TOP_N = 100


def is_market_open():
    now = datetime.now(timezone.utc)
    h, m = now.hour, now.minute
    if h < 13 or h > 20:
        return False
    if h == 13 and m < 30:
        return False
    if h == 20 and m > 0:
        return False
    return True


def send(msg):
    try:
        requests.get(
            f"https://api.telegram.org/bot{TOKEN}/sendMessage",
            params={"chat_id": CHAT_ID, "text": msg},
            timeout=5
        )
    except Exception as e:
        print(f"텔레그램 오류: {e}")


# -----------------------------
# ✅ 전체 미국 주식 심볼 로드
# -----------------------------
def get_all_symbols():
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/stock/symbol",
            params={"exchange": "US", "token": FINNHUB_KEY},
            timeout=15
        ).json()

        if not isinstance(r, list):
            return []

        symbols = [
            x["symbol"] for x in r
            if x.get("type") in ("Common Stock", "EQS")
            and x.get("symbol")
        ]

        print(f"  전체 심볼 수: {len(symbols)}")
        return symbols

    except Exception as e:
        print(f"심볼 로딩 오류: {e}")
        return []


# -----------------------------
# ✅ 병렬 quote 수집 → 상승률 상위 100 추출
# -----------------------------
def fetch_quote(symbol):
    try:
        r = requests.get(
            "https://finnhub.io/api/v1/quote",
            params={"symbol": symbol, "token": FINNHUB_KEY},
            timeout=4
        ).json()

        price = r.get("c")
        prev  = r.get("pc")

        if not price or not prev or prev == 0 or price < 1.0:
            return None

        change = ((price - prev) / prev) * 100
        return (symbol, price, change)

    except:
        return None


def get_top_gainers_direct(all_symbols, n=TOP_N):
    """전체 종목 병렬 quote 조회 → 상승률 상위 N개"""
    results = []

    print(f"  📡 {len(all_symbols)}개 종목 quote 수집 중 (병렬)...")

    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {executor.submit(fetch_quote, s): s for s in all_symbols}
        for future in as_completed(futures):
            data = future.result()
            if data:
                _, _, change = data
                if change > 0:  # 상승 종목만
                    results.append(data)

    # 상승률 내림차순 정렬 → 상위 N개
    results.sort(key=lambda x: x[2], reverse=True)

    print(f"  상승 종목 수: {len(results)}개")
    print(f"  📋 상승률 상위 5 미리보기:")
    for sym, p, c in results[:5]:
        print(f"    {sym}: +{c:.2f}%  ${p:.2f}")

    return results[:n]


def get_volume_ratio(symbol):
    try:
        to_ts   = int(time.time())
        from_ts = to_ts - (20 * 5 * 60)

        r = requests.get(
            "https://finnhub.io/api/v1/stock/candle",
            params={
                "symbol":     symbol,
                "resolution": "5",
                "from":       from_ts,
                "to":         to_ts,
                "token":      FINNHUB_KEY
            },
            timeout=5
        ).json()

        volumes = r.get("v", [])
        if len(volumes) < 6:
            return None

        avg = sum(volumes[:-1]) / len(volumes[:-1])
        return (volumes[-1] / avg) if avg > 0 else 0

    except:
        return None


def get_rsi(symbol):
    try:
        to_ts   = int(time.time())
        from_ts = to_ts - (60 * 5 * 60)

        r = requests.get(
            "https://finnhub.io/api/v1/indicator",
            params={
                "symbol":     symbol,
                "resolution": "5",
                "from":       from_ts,
                "to":         to_ts,
                "indicator":  "rsi",
                "timeperiod": 14,
                "token":      FINNHUB_KEY
            },
            timeout=5
        ).json()

        values = r.get("rsi", [])
        return values[-1] if values else None

    except:
        return None


def score_pump(change, volume_ratio, rsi):
    score = 0

    if 1 <= change <= 3:
        score += 30
    elif 3 < change <= 6:
        score += 20
    elif change > 8:
        score -= 30

    if volume_ratio is not None:
        if volume_ratio >= 4:
            score += 30
        elif volume_ratio >= 3:
            score += 25
        elif volume_ratio >= 2:
            score += 15

    if rsi is None:
        pass
    elif 50 <= rsi <= 60:
        score += 25
    elif 60 < rsi <= 70:
        score += 20
    elif 70 < rsi <= 80:
        score += 5
    else:
        score -= 10

    return max(0, min(score, 100))


alert_times: dict[str, float] = {}

print("🚀 급등 스캐너 시작 (직접 상승률 상위 100 모드)")

# 심볼은 한 번만 로드 (자주 안 바뀜)
all_symbols = []

while True:
    try:
        if not is_market_open():
            print("⛔ 장 마감 — 5분 대기")
            time.sleep(300)
            continue

        # 심볼 없으면 로드
        if not all_symbols:
            print("📂 전체 심볼 로딩...")
            all_symbols = get_all_symbols()
            if not all_symbols:
                print("⚠️ 심볼 로드 실패 — 60초 후 재시도")
                time.sleep(60)
                continue

        # 1단계: 전체 종목 병렬 quote → 상승률 상위 100
        print(f"\n[{datetime.now().strftime('%H:%M:%S')}] 스캔 시작")
        gainers = get_top_gainers_direct(all_symbols, TOP_N)

        if not gainers:
            print("⚠️ 상승 종목 없음 — 60초 후 재시도")
            time.sleep(60)
            continue

        rank_map = {sym: idx + 1 for idx, (sym, _, _) in enumerate(gainers)}
        results = []
        now = time.time()

        # 2단계: 상위 100개에 캔들 + RSI 조회
        for symbol, price, change in gainers:
            time.sleep(0.7)

            vol_ratio = get_volume_ratio(symbol)
            rsi       = get_rsi(symbol)
            prob      = score_pump(change, vol_ratio, rsi)

            vol_str = f"{vol_ratio:.2f}x" if vol_ratio is not None else "N/A"
            rsi_str = f"{rsi:.1f}"        if rsi       is not None else "N/A"

            print(f"#{rank_map[symbol]:3d} {symbol:6s} | {change:+.2f}% | "
                  f"거래량 {vol_str} | RSI {rsi_str} | 점수 {prob}")

            if prob >= 75:
                results.append((symbol, price, change, vol_ratio, rsi, prob))

        results.sort(key=lambda x: x[5], reverse=True)
        print(f"\n🎯 알림 대상: {len(results)}개")

        # 3단계: 알림 발송
        for s, price, change, vol, rsi, prob in results[:5]:
            last_alert    = alert_times.get(s, 0)
            cooldown_left = int((ALERT_COOLDOWN - (now - last_alert)) / 60)

            if now - last_alert < ALERT_COOLDOWN:
                print(f"  ⏭ {s} 쿨다운 중 ({cooldown_left}분 남음)")
                continue

            vol_str = f"{vol:.2f}x" if vol is not None else "N/A"
            rsi_str = f"{rsi:.1f}"  if rsi is not None else "N/A"

            msg = (
                f"🚨 10분 급등 신호\n"
                f"종목: {s}  (상승률 {rank_map[s]}위)\n"
                f"현재가: ${price:.2f}\n"
                f"등락: +{change:.2f}%\n"
                f"RSI: {rsi_str}\n"
                f"거래량: {vol_str}\n"
                f"🔥 점수: {prob}/100"
            )
            print(msg)
            send(msg)
            alert_times[s] = now

        print(f"\n✅ 스캔 완료 — {SCAN_INTERVAL}초 후 재스캔\n")
        time.sleep(SCAN_INTERVAL)

    except Exception as e:
        print(f"루프 오류: {e}")
        time.sleep(15)
