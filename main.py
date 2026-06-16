import os
import requests

token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("CHAT_ID")

url = f"https://api.telegram.org/bot{token}/sendMessage"

requests.get(
    url,
    params={
        "chat_id": chat_id,
        "text": "🚀 Railway 테스트 성공!"
    }
)

print("완료")
