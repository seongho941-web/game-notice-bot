
import json
import os
from pathlib import Path

import requests


API_URL = (
    "https://web-api.kakaogame.com/supportreal/v2/notice"
    "?appId=1329429"
    "&country=KR"
    "&lang=ko"
    "&market=googlePlay"
    "&type=notice"
    "&cnt=10"
)

STATE_FILE = Path("seen_posts.json")


def load_seen():
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
        if isinstance(data, list):
            return set(str(item) for item in data)
    except (OSError, json.JSONDecodeError):
        pass

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
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json, text/plain, */*",
        },
        timeout=30,
    )

    print("API 응답 코드:", response.status_code)
    response.raise_for_status()

    data = response.json()

    print("API 응답 최상위 항목:", list(data.keys()) if isinstance(data, dict) else type(data).__name__)

    # API 응답 구조에 따라 공지 목록 추출
    posts = None

    if isinstance(data, list):
        posts = data
    elif isinstance(data, dict):
        for key in ("data", "result", "noticeList", "list", "notices", "items"):
            value = data.get(key)

            if isinstance(value, list):
                posts = value
                break

            if isinstance(value, dict):
                for nested_key in ("list", "noticeList", "notices", "items"):
                    nested_value = value.get(nested_key)
                    if isinstance(nested_value, list):
                        posts = nested_value
                        break

            if posts is not None:
                break

    if posts is None:
        print("공지 목록 구조를 자동으로 찾지 못했습니다.")
        print("응답 일부:", json.dumps(data, ensure_ascii=False)[:1500])
        return []

    notices = []

    for post in posts:
        if not isinstance(post, dict):
            continue

        post_id = (
            post.get("seq")
            or post.get("noticeSeq")
            or post.get("id")
            or post.get("noticeId")
            or post.get("postId")
        )

        title = (
            post.get("title")
            or post.get("noticeTitle")
            or post.get("subject")
            or ""
        ).strip()

        url = (
            f"https://bbs.kakaogames.com/ko/1329429/notice/detail?id={post_id}"
        )

        if not post_id or not title:
            continue

        if url and url.startswith("/"):
            url = "https://web-api.kakaogame.com" + url

        notices.append({
            "id": str(post_id),
            "title": title,
            "url": url,
        })

    print(f"[도깨비의 세계] 공지 {len(notices)}개 수집")

    for notice in notices[:5]:
        print(f" - 제목: {notice['title']}")
        print(f"   ID: {notice['id']}")
        print(f"   URL: {notice['url']}")

    return notices


def send_notice(notice, webhook):
    url = notice["url"]

    if not url:
        url = (
            "https://bbs.kakaogames.com/ko/1329429/notice"
        )

    message = f"{notice['title']}\n{url}"

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
        raise RuntimeError(
            "공지 목록을 찾지 못했습니다. API 응답 구조를 확인해야 합니다."
        )

    if not seen:
        # 최초 실행은 최신 공지 하나만 테스트 전송
        send_notice(notices[0], webhook)
        seen.update(notice["id"] for notice in notices)
    else:
        new_notices = [
            notice
            for notice in notices
            if notice["id"] not in seen
        ]

        for notice in reversed(new_notices):
            send_notice(notice, webhook)
            seen.add(notice["id"])

        if not new_notices:
            print("새 공지가 없습니다.")

    save_seen(seen)
    print("공지 확인 완료.")


if __name__ == "__main__":
    main()
