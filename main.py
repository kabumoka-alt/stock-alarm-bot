import os
import requests

token = os.environ.get("TELEGRAM_TOKEN")
chat_id = os.environ.get("CHAT_ID")

if not token or not chat_id:
    print("환경변수 없음")
    exit(1)

url = f"https://api.telegram.org/bot{token}/sendMessage"

try:
    requests.get(url, params={
        "chat_id": chat_id,
        "text": "🚀 Railway 정상 실행됨"
    })
    print("success")
except Exception as e:
    print("error:", e)
