
import json
import os
import sys
from pathlib import Path

import requests
from bs4 import BeautifulSoup


NOTICE_URL = "https://mabinogimobile.nexon.com/News/Notice"
WEBHOOK_URL = os.getenv("MOBINOGI_NOTICE_WEBHOOK")
STATE_FILE = Path("mobinogi_seen_posts.json")


def fetch_notices():
    """모비노기 공지 목록에서 제목과 링크를 가져온다."""
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/130.0.0.0 Safari/537.36"
        )
    }

    response = requests.get(
        NOTICE_URL,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    notices = []

    for item in soup.select("ul.list > li.item"):
        link = item.select_one('a[href*="/News/Notice/"]')

        if not link:
            continue

        title_element = link.select_one("span")

        if not title_element:
            continue

        title = title_element.get_text(" ", strip=True)
        href = link.get("href", "").strip()

        if not title or not href:
            continue

        if href.startswith("/"):
            url = "https://mabinogimobile.nexon.com" + href
        elif href.startswith("https://"):
            url = href
        else:
            continue

        notices.append({
            "id": href.rstrip("/").split("/")[-1],
            "title": title,
            "url": url,
        })

    if not notices:
        raise RuntimeError(
            "공지 목록을 찾지 못했습니다. "
            "HTML 구조가 변경되었거나 응답에 공지 목록이 없을 수 있습니다."
        )

    return notices


def load_seen_posts():
    """기존에 확인한 공지 ID를 불러온다."""
    if not STATE_FILE.exists():
        return None

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data.get("seen_ids", []))
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(
            f"공지 기록 파일을 읽을 수 없습니다: {error}"
        ) from error


def save_seen_posts(seen_ids):
    """공지 ID 목록을 파일에 저장한다."""
    data = {
        "seen_ids": sorted(seen_ids),
    }

    temporary_file = STATE_FILE.with_suffix(".tmp")
    temporary_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temporary_file.replace(STATE_FILE)


def send_discord_message(notice):
    """새 공지를 전용 Discord 웹훅으로 전송한다."""
    if not WEBHOOK_URL:
        raise RuntimeError(
            "GitHub Secrets에 MOBINOGI_NOTICE_WEBHOOK을 설정해 주세요."
        )

    message = (
        "📢 **모비노기 공지**\n"
        f"{notice['title']}\n"
        f"{notice['url']}"
    )

    response = requests.post(
        WEBHOOK_URL,
        json={
            "content": message,
            "allowed_mentions": {"parse": []},
        },
        timeout=30,
    )

    if not response.ok:
        print("Discord 응답 코드:", response.status_code)
        print("Discord 응답 내용:", response.text)
        response.raise_for_status()


def main():
    print("[시작] 모비노기 공지 확인")

    notices = fetch_notices()
    seen_ids = load_seen_posts()

    current_ids = {notice["id"] for notice in notices}

    # 최초 실행: 기존 공지만 기록하고 알림은 보내지 않는다.
    if seen_ids is None:
        save_seen_posts(current_ids)
        print(
            f"[초기 등록 완료] 기존 공지 {len(current_ids)}개를 저장했습니다. "
            "이번 실행에서는 알림을 보내지 않습니다."
        )
        return

    new_notices = [
        notice
        for notice in notices
        if notice["id"] not in seen_ids
    ]

    if not new_notices:
        print("[완료] 새 공지가 없습니다.")
        return

    # 목록이 최신순으로 표시되므로 오래된 새 공지부터 전송한다.
    for notice in reversed(new_notices):
        print(f"[새 공지] {notice['title']}")

        send_discord_message(notice)

        # 전송 성공한 공지만 기록한다.
        seen_ids.add(notice["id"])
        save_seen_posts(seen_ids)

        print(f"[전송 성공] {notice['url']}")

    print(f"[완료] 새 공지 {len(new_notices)}개를 전송했습니다.")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(f"[오류] {error}")
        sys.exit(1)
