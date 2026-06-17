import os
import requests
import time
from datetime import datetime, timezone

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


def get_top_gainers(n=TOP_N):
   """Yahoo Finance 스크리너 — 당일 상승률 상위 N개"""
   try:
       url = "https://query1.finance.yahoo.com/v1/finance/screener/predefined/saved"
       params = {
           "scrIds": "day_gainers",
           "count": n,
           "lang": "en-US",
           "region": "US"
       }
       headers = {"User-Agent": "Mozilla/5.0"}

       r = requests.get(url, params=params, headers=headers, timeout=10).json()

       quotes = (
           r.get("finance", {})
            .get("result", [{}])[0]
            .get("quotes", [])
       )

       result = []
       for q in quotes:
           symbol = q.get("symbol", "")
           price  = q.get("regularMarketPrice")
           change = q.get("regularMarketChangePercent")

           if not symbol or price is None or change is None:
               continue

           result.append((symbol, price, change))

       # Yahoo가 이미 정렬해서 주지만 한 번 더 보장
       result.sort(key=lambda x: x[2], reverse=True)

       print(f"📋 상승률 상위 5 미리보기:")
       for sym, p, c in result[:5]:
           print(f"  {sym}: +{c:.2f}%  ${p:.2f}")

       return result

   except Exception as e:
       print(f"스크리너 오류: {e}")
       return []


def get_volume_ratio(symbol):
   """현재 5분봉 거래량 / 직전 19개 평균"""
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
   """5분봉 RSI(14) 최신값"""
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

   # 등락률
   if 1 <= change <= 3:
       score += 30
   elif 3 < change <= 6:
       score += 20
   elif change > 8:
       score -= 30  # 이미 과열

   # 거래량 비율
   if volume_ratio is not None:
       if volume_ratio >= 4:
           score += 30
       elif volume_ratio >= 3:
           score += 25
       elif volume_ratio >= 2:
           score += 15

   # RSI
   if rsi is None:
       pass  # 데이터 없으면 중립
   elif 50 <= rsi <= 60:
       score += 25
   elif 60 < rsi <= 70:
       score += 20
   elif 70 < rsi <= 80:
       score += 5
   else:
       score -= 10

   return max(0, min(score, 100))


# 종목별 마지막 알림 시각
alert_times: dict[str, float] = {}

print("🚀 급등 스캐너 시작 (당일 상승률 상위 100 모드)")

while True:
   try:
       if not is_market_open():
           print("⛔ 장 마감 — 5분 대기")
           time.sleep(300)
           continue

       # 1단계: 상승률 상위 100 종목 가져오기
       gainers = get_top_gainers(TOP_N)
       print(f"\n📊 {len(gainers)}개 종목 스캔 시작")

       if not gainers:
           print("⚠️ 종목 로드 실패 — 60초 후 재시도")
           time.sleep(60)
           continue

       # 순위 조회용 딕셔너리
       rank_map = {sym: idx + 1 for idx, (sym, _, _) in enumerate(gainers)}

       results = []
       now = time.time()

       # 2단계: 캔들 + RSI 추가 조회 (quote는 Yahoo에서 이미 확보)
       for symbol, price, change in gainers:
           time.sleep(0.7)  # Finnhub 분당 ~85호출 유지

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

       # 3단계: 상위 5개 알림 발송
       for s, price, change, vol, rsi, prob in results[:5]:
           last_alert = alert_times.get(s, 0)
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
