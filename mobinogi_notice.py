
import json
import os
import sys
from pathlib import Path

import requests

# 마비노기 모바일 공식 공지 API
API_URL = (
    "https://forum.nexon.com/api/v1/board/4557/threads"
    "?pageNo=1&paginationType=PAGING&pageSize=10"
)

WEBHOOK_URL = os.getenv("MOBINOGI_NOTICE_WEBHOOK")
STATE_FILE = Path("mobinogi_seen_posts.json")

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
}


def fetch_notices():
    """공식 공지 API에서 게시물 ID와 제목을 가져온다."""
    response = requests.get(API_URL, headers=HEADERS, timeout=30)

    print(f"[진단] HTTP 상태 코드: {response.status_code}")
    print(f"[진단] 최종 응답 주소: {response.url}")

    response.raise_for_status()
    data = response.json()

    threads = data.get("threads", [])
    notices = []

    for thread in threads:
        thread_id = str(thread.get("threadId", "")).strip()
        title = str(thread.get("title", "")).strip()

        if not thread_id or not title:
            continue

        # 삭제되었거나 공개 상태가 아닌 게시물은 제외
        if thread.get("isDelete", False):
            continue
        if thread.get("release") != "ON":
            continue
        if thread.get("isWebHide", False):
            continue

        notices.append({
            "id": thread_id,
            "title": title.replace("&amp;", "&"),
            "url": (
                "https://mabinogimobile.nexon.com/"
                f"News/Notice/{thread_id}"
            ),
        })

    if not notices:
        raise RuntimeError(
            "공지 목록이 비어 있습니다. API 응답을 확인해 주세요."
        )

    print(f"[진단] 공지 {len(notices)}개 발견")
    print(f"[진단] 게시판: {data.get('boardTitle', '(확인 불가)')}")

    return notices


def load_seen_posts():
    """기존에 기록한 게시물 ID를 읽는다."""
    if not STATE_FILE.exists():
        return None

    try:
        with STATE_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if not isinstance(data, list):
            raise ValueError("기록 파일 형식이 올바르지 않습니다.")

        return {str(post_id) for post_id in data}

    except (json.JSONDecodeError, ValueError) as error:
        raise RuntimeError(
            f"공지 기록 파일을 읽을 수 없습니다: {error}"
        ) from error


def save_seen_posts(seen_posts):
    """게시물 ID를 파일에 저장한다."""
    with STATE_FILE.open("w", encoding="utf-8") as file:
        json.dump(
            sorted(seen_posts, key=int),
            file,
            ensure_ascii=False,
            indent=2,
        )


def send_discord_message(notice):
    """공지 제목과 링크만 디스코드로 보낸다."""
    if not WEBHOOK_URL:
        raise RuntimeError(
            "MOBINOGI_NOTICE_WEBHOOK 시크릿이 설정되지 않았습니다."
        )

    message = f"**{notice['title']}**\n{notice['url']}"

    response = requests.post(
        WEBHOOK_URL,
        json={"content": message},
        timeout=30,
    )
    response.raise_for_status()


def main():
    print("[시작] 마비노기 모바일 공지 확인")

    notices = fetch_notices()
    seen_posts = load_seen_posts()

    # 최초 실행은 현재 공지를 기록만 하고 전송하지 않는다.
    if seen_posts is None:
        save_seen_posts({notice["id"] for notice in notices})
        print(
            f"[초기화] 기존 공지 {len(notices)}개를 기록했습니다. "
            "이번 실행에서는 전송하지 않습니다."
        )
        return

    new_notices = [
        notice for notice in reversed(notices)
        if notice["id"] not in seen_posts
    ]

    if not new_notices:
        print("[완료] 새 공지가 없습니다.")
        return

    for notice in new_notices:
        send_discord_message(notice)
        seen_posts.add(notice["id"])
        save_seen_posts(seen_posts)
        print(f"[전송 성공] {notice['title']}")

    print(f"[완료] 새 공지 {len(new_notices)}개 전송")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"[오류] {error}")
        sys.exit(1)
