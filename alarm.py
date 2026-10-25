
import os
import sys

import requests


WEBHOOK_URL = os.getenv("ALARM_WEBHOOK")
SCHEDULE = os.getenv("ALARM_SCHEDULE", "")

ALARMS = {
    "45 11 * * *": {
        "name": "도깨비 필드보스",
        "message": "도깨비 필드보스 시간 @here",
    },
    "45 12 * * *": {
        "name": "도깨비 낙화의전장",
        "message": "도깨비 낙화의전장 시간 @here",
    },
    "0 13 * * 2": {
        "name": "도깨비 주간컨텐츠 점검",
        "message": "도깨비 주간컨텐츠 점검 시간 @here",
    },
    "0 11 * * 5": {
        "name": "도깨비 신기쟁탈전",
        "message": "도깨비 신기쟁탈전 시간 @here",
    },
    "10 11 * * 6": {
        "name": "도깨비 미혹의정원",
        "message": "도깨비 미혹의정원 시간 @here",
    },
}


def main():
    if not WEBHOOK_URL:
        raise RuntimeError(
            "GitHub Secrets에 ALARM_WEBHOOK을 설정해 주세요."
        )

    alarm = ALARMS.get(SCHEDULE)

    if alarm is None:
        raise RuntimeError(
            f"알 수 없는 예약 시간입니다: {SCHEDULE!r}"
        )

    print(f"[알람 시작] {alarm['name']}")
    print(f"예약 표현식(UTC): {SCHEDULE}")

    response = requests.post(
        WEBHOOK_URL,
        json={
            "content": alarm["message"],
            "allowed_mentions": {
                "parse": ["everyone"]
            },
        },
        timeout=20,
    )

    if not response.ok:
        print("Discord 응답:", response.status_code)
        print("응답 내용:", response.text)
        response.raise_for_status()

    print(f"[전송 성공] {alarm['message']}")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"[알람 오류] {error}")
        sys.exit(1)

