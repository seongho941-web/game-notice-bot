
import os
import requests

def main():
    targets = [
        ("마비노기 모바일", "MABI_WEBHOOK"),
        ("도깨비의세계", "DOKKAEBI_WEBHOOK"),
    ]

    for game, secret_name in targets:
        webhook = os.getenv(secret_name)

        if not webhook:
            print(f"[설정 확인 필요] {game}: {secret_name}")
            continue

        try:
            response = requests.post(
                webhook,
                json={
                    "content": f"✅ {game} 공지봇 연결 테스트입니다.",
                    "allowed_mentions": {"parse": []},
                },
                timeout=20,
            )
            response.raise_for_status()
            print(f"[성공] {game} 웹훅 연결")
        except requests.RequestException as exc:
            print(f"[실패] {game} 웹훅 연결: {exc}")
            raise

if __name__ == "__main__":
    main()
