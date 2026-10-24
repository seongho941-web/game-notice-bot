
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

NOTICE_URL = (
    "https://bbs.kakaogames.com/ko/1329429/"
    "notice/detail?id={}"
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
            return {str(item) for item in data}
    except (OSError, json.JSONDecodeError):
        print("중복 방지 기록을 읽지 못했습니다.")

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
    print("[도깨비의 세계] 공지 확인 시작")

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

    if not isinstance(data, dict):
        raise RuntimeError("공지 API 응답 형식이 예상과 다릅니다.")

    if data.get("code") not in (None, 0, "0", "SUCCESS", "success"):
        raise RuntimeError(
            f"공지 API 오류: {data.get('code')} / "
            f"{data.get('message')}"
        )

    posts = data.get("noticeList")

    if not isinstance(posts, list):
        raise RuntimeError("공지 목록을 찾을 수 없습니다.")

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

        if post_id is None or not title:
            continue

        post_id = str(post_id)

        notices.append({
            "id": post_id,
            "title": title,
            "url": NOTICE_URL.format(post_id),
        })

    # 최신 공지가 앞에 오도록 ID 기준으로 정렬하지 않고
    # API가 반환한 순서를 그대로 유지합니다.
    print(f"공지 {len(notices)}개 수집")

    for notice in notices:
        print(f" - [{notice['id']}] {notice['title']}")

    return notices


def send_notice(notice, webhook):
    message = f"📢 **도깨비의 세계 공지**\n{notice['title']}\n{notice['url']}"

    response = requests.post(
        webhook,
        json={
            "content": message,
            "allowed_mentions": {"parse": []},
        },
        timeout=20,
    )

    response.raise_for_status()
    print(f"[전송 성공] {notice['id']}: {notice['title']}")


def main():
    webhook = os.getenv("DOKKAEBI_WEBHOOK")

    if not webhook:
        raise RuntimeError(
            "GitHub Secrets의 DOKKAEBI_WEBHOOK을 확인해 주세요."
        )

    seen = load_seen()
    notices = get_notices()

    if not notices:
        print("확인할 공지가 없습니다.")
        return

    # 첫 실행이거나 기록이 없는 경우 현재 공지를 기준점으로 저장합니다.
    # 기존 공지를 한꺼번에 다시 전송하지 않습니다.
    if not seen:
        seen.update(notice["id"] for notice in notices)
        save_seen(seen)
        print("최초 실행: 기존 공지를 기준점으로 저장했습니다.")
        return

    new_notices = [
        notice for notice in notices
        if notice["id"] not in seen
    ]

    if not new_notices:
        print("새 공지가 없습니다.")
        return

    # API가 최신 공지부터 반환한다고 가정하고,
    # 새 공지는 오래된 것부터 전송합니다.
    for notice in reversed(new_notices):
        send_notice(notice, webhook)

        # 성공적으로 전송한 공지만 즉시 기록합니다.
        seen.add(notice["id"])
        save_seen(seen)

    print(f"새 공지 {len(new_notices)}개 전송 완료")


if __name__ == "__main__":
    main()
