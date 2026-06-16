import os
import requests
import time

token = os.getenv("TELEGRAM_TOKEN")
chat_id = os.getenv("CHAT_ID")

while True:
    try:
        requests.get(
            f"https://api.telegram.org/bot{token}/sendMessage",
            params={
                "chat_id": chat_id,
                "text": "🚀 Railway 살아있음 테스트"
            }
        )
        print("sent")
    except Exception as e:
        print(e)

    time.sleep(60)
