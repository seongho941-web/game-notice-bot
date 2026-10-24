
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup


BASE_URL = "https://bbs.kakaogames.com"
NOTICE_URL = f"{BASE_URL}/ko/1329429/notice"
STATE_FILE = Path("seen_posts.json")


def load_seen():
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(
            STATE_FILE.read_text(encoding="utf-8")
        )
        return set(str(item) for item in data) if isinstance(data, list) else set()
    except (OSError, json.JSONDecodeError):
        return set()


def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_notices():
    print("[도깨비의 세계] 공식 공지 페이지 요청")

    response = requests.get(
        NOTICE_URL,
        headers={
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/130.0.0.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml",
        },
        timeout=30,
    )

    print("페이지 응답 코드:", response.status_code)
    response.raise_for_status()

    soup = BeautifulSoup(response.text, "html.parser")
    notices = []
    found_ids = set()

    for link in soup.find_all("a", href=True):
        href = link["href"]

        if "/ko/1329429/notice/detail" not in href:
            continue

        match = re.search(r"[?&]id=(\d+)", href)
        if not match:
            continue

        post_id = match.group(1)

        if post_id in found_ids:
            continue

        title = " ".join(link.get_text(" ", strip=True).split())

        if not title:
            title = link.get("title", "").strip()

        if not title:
            continue

        found_ids.add(post_id)

        notices.append({
            "id": post_id,
            "title": title,
            "url": urljoin(BASE_URL, href),
        })

    print(f"[도깨비의 세계] 공지 {len(notices)}개 수집")

    for notice in notices[:5]:
        print(f" - {notice['title']} | {notice['url']}")

    if not notices:
        print("공지 링크를 찾지 못했습니다.")
        print("페이지 내용 일부:", soup.get_text(" ", strip=True)[:500])

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
            "GitHub Secrets의 DOKKAEBI_WEBHOOK 설정을 확인해 주세요."
        )

    seen = load_seen()
    notices = get_notices()

    if not notices:
        raise RuntimeError(
            "공지 목록을 찾지 못했습니다. 페이지 접근 또는 HTML 구조를 확인해야 합니다."
        )

    if not seen:
        # 최초 실행은 최신 공지 하나만 테스트 전송
        send_notice(notices[0], webhook)
        seen.update(notice["id"] for notice in notices)
    else:
        new_notices = [
            notice for notice in notices
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
