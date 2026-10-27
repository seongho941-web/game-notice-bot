
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
        ),
        "Accept-Language": "ko-KR,ko;q=0.9,en;q=0.8",
    }


    response = requests.get(
        NOTICE_URL,
        headers=headers,
        timeout=30,
    )
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")

    print(f"[진단] HTTP 상태 코드: {response.status_code}")
    print(f"[진단] 응답 길이: {len(response.text)}")
    print(
        "[진단] 페이지 제목:",
        soup.title.get_text(strip=True) if soup.title else "(없음)",
    )
    print(f"[진단] ul.list 개수: {len(soup.select('ul.list'))}")
    print(f"[진단] li.item 개수: {len(soup.select('li.item'))}")
    print(
        "[진단] 공지 링크 개수:",
        len(soup.select('a[href*="/News/Notice/"]')),
    )

    notices = []

    for item in soup.select("ul.list > li.item"):
        link = item.select_one('a[href*="/News/Notice/"]')

        if not link:
            continue

        # 게시글 제목은 링크 안의 span에서 가져온다.
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

        post_id = href.rstrip("/").split("/")[-1]

        if not post_id:
            continue

        notices.append({
            "id": post_id,
            "title": title,
            "url": url,
        })

    # 중복된 게시글 ID는 한 번만 유지한다.
    unique_notices = []
    found_ids = set()

    for notice in notices:
        if notice["id"] not in found_ids:
            found_ids.add(notice["id"])
            unique_notices.append(notice)

    if not unique_notices:
        print("[진단] 공지 목록을 찾지 못했습니다.")
        print("[진단] 응답 앞부분:")
        print(response.text[:1500])

        raise RuntimeError(
            "공지 목록을 찾지 못했습니다. "
            "실행 로그에서 HTML 구조를 확인해 주세요."
        )

    print(f"[진단] 공지 {len(unique_notices)}개 발견")

    for notice in unique_notices[:5]:
        print(f"[진단] 제목: {notice['title']}")

    return unique_notices


def load_seen_posts():
    """저장된 공지 기록을 읽는다."""
    if not STATE_FILE.exists():
        print("[기록] 기존 공지 기록 파일이 없습니다.")
        return None

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as error:
        raise RuntimeError(
            f"공지 기록 파일을 읽지 못했습니다: {error}"
        ) from error

    seen_ids = data.get("seen_ids")

    if not isinstance(seen_ids, list):
        raise RuntimeError(
            "공지 기록 파일에 seen_ids 목록이 없습니다."
        )

    print(f"[기록] 기존 공지 ID {len(seen_ids)}개를 불러왔습니다.")
    return set(str(post_id) for post_id in seen_ids)


def save_seen_posts(seen_ids):
    """공지 ID를 JSON 파일로 저장한다."""
    data = {
        "seen_ids": sorted(seen_ids),
    }

    temporary_file = STATE_FILE.with_suffix(".tmp")

    temporary_file.write_text(
        json.dumps(data, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    temporary_file.replace(STATE_FILE)

    print(
        f"[기록] {STATE_FILE} 저장 완료 "
        f"(공지 ID {len(seen_ids)}개)"
    )


def send_discord_message(notice):
    """새 공지를 Discord로 전송한다."""
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
        print("[Discord 오류] 상태 코드:", response.status_code)
        print("[Discord 오류] 응답:", response.text)
        response.raise_for_status()


def main():
    print("[시작] 모비노기 공지 확인")

    notices = fetch_notices()
    seen_ids = load_seen_posts()

    current_ids = {notice["id"] for notice in notices}

    # 최초 실행: 기존 공지 목록을 기록하고 알림은 보내지 않는다.
    if seen_ids is None:
        save_seen_posts(current_ids)

        print(
            f"[초기 등록 완료] 기존 공지 {len(current_ids)}개를 저장했습니다. "
            "이번 실행에서는 Discord 알림을 보내지 않습니다."
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

    # 목록이 최신순이라면 새 공지들을 오래된 순서부터 전송한다.
    for notice in reversed(new_notices):
        print(f"[새 공지] {notice['title']}")

        send_discord_message(notice)

        # Discord 전송에 성공한 게시글만 기록한다.
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
