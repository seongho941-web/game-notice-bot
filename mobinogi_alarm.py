
import os
import sys

import requests


WEBHOOK_URL = os.getenv("MOBINOGI_WEBHOOK")


def main():
    if not WEBHOOK_URL:
        raise RuntimeError(
            "GitHub Secrets에 MOBINOGI_WEBHOOK을 설정해 주세요."
        )

    message = "모비노기 주간컨텐츠 점검 시간 @here"

    response = requests.post(
        WEBHOOK_URL,
        json={
            "content": message,
            "allowed_mentions": {"parse": []},
        },
        timeout=20,
    )

    if not response.ok:
        print("Discord 응답:", response.status_code)
        print("응답 내용:", response.text)
        response.raise_for_status()

    print(f"[전송 성공] {message}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"[알람 오류] {error}")
        sys.exit(1)
