
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

    except (OSError, json.JSONDecodeError) as error:
        print(f"중복 방지 기록 읽기 실패: {error}")
        raise

    raise RuntimeError(
        "seen_posts.json 형식이 올바르지 않습니다."
    )


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
        raise RuntimeError(
            "공지 API 응답 형식이 예상과 다릅니다."
        )

    api_code = str(data.get("code", "")).strip().lower()
    api_message = str(data.get("message", "")).strip().lower()

    # 실제 API의 성공 응답: code=200, message=success
    if (
        api_code not in ("", "0", "200", "success")
        and api_message != "success"
    ):
        raise RuntimeError(
            f"공지 API 오류: {data.get('code')} / "
            f"{data.get('message')}"
        )

    posts = data.get("noticeList")

    if not isinstance(posts, list):
        raise RuntimeError(
            "공지 목록을 찾을 수 없습니다."
        )

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

    print(f"공지 {len(notices)}개 수집")

    for notice in notices[:5]:
        print(f" - 제목: {notice['title']}")
        print(f"   ID: {notice['id']}")
        print(f"   URL: {notice['url']}")

    if not notices:
        raise RuntimeError(
            "공지 목록이 비어 있습니다."
        )

    return notices


def send_notice(notice, webhook):
    message = (
        f"📢 **도깨비의 세계 공지**\n"
        f"{notice['title']}\n"
        f"{notice['url']}"
    )

    response = requests.post(
        webhook,
        json={
            "content": message,
            "allowed_mentions": {"parse": []},
        },
        timeout=20,
    )

    response.raise_for_status()

    print(
        f"[전송 성공] {notice['id']}: "
        f"{notice['title']}"
    )


def main():
    webhook = os.getenv("DOKKAEBI_WEBHOOK")

    if not webhook:
        raise RuntimeError(
            "GitHub Secrets의 DOKKAEBI_WEBHOOK을 "
            "확인해 주세요."
        )

    seen = load_seen()
    notices = get_notices()

    # 기록이 없는 최초 실행은 기존 공지를 기준점으로 저장합니다.
    if not seen:
        seen.update(
            notice["id"] for notice in notices
        )
        save_seen(seen)

        print(
            "최초 실행: 기존 공지를 기록했습니다. "
            "새 공지가 올라오면 전송합니다."
        )
        return

    new_notices = [
        notice
        for notice in notices
        if notice["id"] not in seen
    ]

    if not new_notices:
        print("새 공지가 없습니다.")
        return

    # API가 최신 공지부터 반환하므로 오래된 공지부터 전송합니다.
    for notice in reversed(new_notices):
        send_notice(notice, webhook)

        # 전송 성공한 공지만 기록합니다.
        seen.add(notice["id"])
        save_seen(seen)

    print(
        f"새 공지 {len(new_notices)}개 전송 완료"
    )


if __name__ == "__main__":
    main()
