import os
import requests

token = os.environ.get("TELEGRAM_TOKEN")
chat_id = os.environ.get("CHAT_ID")

url = f"https://api.telegram.org/bot{token}/sendMessage"

requests.get(
    url,
    params={
        "chat_id": chat_id,
        "text": "🚀 Railway 정상 실행됨"
    }
)

print("success")
