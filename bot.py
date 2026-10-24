
import json
import os
from pathlib import Path

import requests

STATE_FILE = Path("seen_posts.json")

API_URL = (
    "https://forum-api.kakaogames.com/"
    "v1/dokkaebi/boards/notice/list?lang=ko&size=18"
)

POST_URL = (
    "https://forum.kakaogames.com/dokkaebi/postView/"
)


def load_seen():
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
        return set(data) if isinstance(data, list) else set()
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps(
            sorted(seen),
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def get_notices():
    print("[도깨비의 세계] 공지 API 요청")

    response = requests.get(
        API_URL,
        headers={"User-Agent": "Mozilla/5.0"},
        timeout=30,
    )
    response.raise_for_status()

    data = response.json()
    posts = data.get("posts")

    if posts is None:
        posts = data.get("data", {}).get("posts", [])

    notices = []

    for post in posts:
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
    webhook = os.getenv("DOKKAEBI_WEBHOOK")

    if not webhook:
        raise RuntimeError(
            "GitHub Secrets의 DOKKAEBI_WEBHOOK을 확인해 주세요."
        )

    seen = load_seen()
    notices = get_notices()

    if not notices:
        print("공지 목록이 비어 있습니다.")
        return

    # 최초 실행: 최신 공지 하나를 테스트 전송하고
    # 현재 목록을 기록해 중복 전송을 방지
    if not seen:
        send_notice(notices[0], webhook)
        seen.update(notice["id"] for notice in notices)
    else:
        new_notices = [
            notice for notice in notices
            if notice["id"] not in seen
        ]

        # 새 공지가 여러 개라면 오래된 것부터 전송
        for notice in reversed(new_notices):
            send_notice(notice, webhook)
            seen.add(notice["id"])

    save_seen(seen)


if __name__ == "__main__":
    main()
