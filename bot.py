
import json
import os
from pathlib import Path

import requests


# 공지 목록 API 주소
API_URL = (
    "https://forum-api.kakaogames.com/"
    "v1/dokkaebi/boards/notice/list?lang=ko&size=18"
)

# 공지 상세 페이지 주소
POST_URL = "https://forum.kakaogames.com/dokkaebi/postView/"

# 이미 전송한 공지 ID를 저장하는 파일
STATE_FILE = Path("seen_posts.json")


def load_seen():
    """이미 전송한 공지 ID 목록 불러오기."""
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )

        if isinstance(data, list):
            return set(str(item) for item in data)

        return set()

    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen):
    """전송한 공지 ID 목록 저장하기."""
    STATE_FILE.write_text(
        json.dumps(
            sorted(seen),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_notices():
    """공식 공지 API에서 공지 목록 가져오기."""
    print("[도깨비의 세계] 공지 API 요청")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        ),
        "Accept": "application/json, text/plain, */*",
        "Origin": "https://forum.kakaogames.com",
        "Referer": "https://forum.kakaogames.com/dokkaebi/",
    }

    response = requests.get(
        API_URL,
        headers=headers,
        timeout=30,
    )

    print("API 응답 코드:", response.status_code)

    if response.status_code != 200:
        print("API 응답 내용:", response.text[:500])

    response.raise_for_status()

    data = response.json()

    posts = data.get("posts")

    if posts is None:
        nested_data = data.get("data", {})
        if isinstance(nested_data, dict):
            posts = nested_data.get("posts", [])

    if not isinstance(posts, list):
        print("공지 목록 형식이 예상과 다릅니다.")
        print("API 응답 일부:", str(data)[:500])
        return []

    notices = []

    for post in posts:
        if not isinstance(post, dict):
            continue

        post_id = post.get("post_id")
        title = (post.get("title") or "").strip()

        if not post_id or not title:
            continue

        url = f"{POST_URL}?code=notice&id={post_id}"

        notices.append({
            "id": str(post_id),
            "title": title,
            "url": url,
        })

    print(f"[도깨비의 세계] 공지 {len(notices)}개 수집")

    for notice in notices[:5]:
        print(f" - {notice['title']} | {notice['url']}")

    return notices


def send_notice(notice, webhook):
    """공지 제목과 링크를 디스코드로 전송하기."""
    message = f"{notice['title']}\n{notice['url']}"

    response = requests.post(
        webhook,
        json={
            "content": message,
            "allowed_mentions": {"parse": []},
        },
        timeout=20,
    )

    response.raise_for_status()

    print(f"[전송 성공] {notice['title']}")


def main():
    """공지 확인 및 새 공지 전송."""
    webhook = os.getenv("DOKKAEBI_WEBHOOK")

    if not webhook:
        raise RuntimeError(
            "GitHub Secrets에 DOKKAEBI_WEBHOOK이 설정되어 있는지 확인해 주세요."
        )

    seen = load_seen()
    notices = get_notices()

    if not notices:
        print("공지 목록이 비어 있습니다. 전송하지 않았습니다.")
        return

    # 최초 실행 시 최신 공지 하나를 테스트 전송
    if not seen:
        latest_notice = notices[0]
        send_notice(latest_notice, webhook)

        seen.update(
            notice["id"] for notice in notices
        )

    else:
        # 아직 전송하지 않은 공지만 골라내기
        new_notices = [
            notice
            for notice in notices
            if notice["id"] not in seen
        ]

        if not new_notices:
            print("새 공지가 없습니다.")
        else:
            # 오래된 새 공지부터 순서대로 전송
            for notice in reversed(new_notices):
                send_notice(notice, webhook)
                seen.add(notice["id"])

    save_seen(seen)
    print("공지 확인 완료.")


if __name__ == "__main__":
    main()
