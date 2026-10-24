
import json
import os
from pathlib import Path
from urllib.parse import urljoin, urldefrag

import requests
from playwright.sync_api import sync_playwright

STATE_FILE = Path("seen_posts.json")

NOTICE_URL = (
    "https://forum.kakaogames.com/"
    "dokkaebi/postList/?code=notice"
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


def get_notices(page):
    print(f"[도깨비의 세계] 공지 페이지 접속: {NOTICE_URL}")

    try:
        page.goto(
            NOTICE_URL,
            wait_until="domcontentloaded",
            timeout=60000,
        )
        page.wait_for_timeout(5000)
    except Exception as exc:
        print(f"[도깨비의 세계] 페이지 접속 실패: {exc}")
        return []

    print(f"[도깨비의 세계] 최종 주소: {page.url}")
    print(f"[도깨비의 세계] 페이지 제목: {page.title()}")

    notices = []
    found = set()

    for a in page.locator("a[href]").all():
        try:
            href = a.get_attribute("href")
            title = a.inner_text().strip()

            if not href or not title:
                continue

            link = urldefrag(urljoin(page.url, href))[0]
            low = link.lower()

            # 공지사항 상세 게시글만 수집
            if "postview" not in low:
                continue
            if "code=notice" not in low:
                continue

            if link in found:
                continue

            found.add(link)
            notices.append({
                "title": title,
                "url": link,
            })

        except Exception:
            continue

    print(f"[도깨비의 세계] 공지 {len(notices)}개 발견")

    for notice in notices[:5]:
        print(f" - {notice['title']} | {notice['url']}")

    return notices


def send_notice(notice, webhook):
    # 디스코드에는 제목과 링크만 전송
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
            "GitHub Secrets에 DOKKAEBI_WEBHOOK이 설정되어 있는지 확인해 주세요."
        )

    seen = load_seen()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="ko-KR")

        notices = get_notices(page)

        if not notices:
            print(
                "[도깨비의 세계] 공지를 찾지 못했습니다. "
                "페이지 주소와 링크 형식을 확인해야 합니다."
            )
            browser.close()
            return

        # 첫 실행: 최신 공지 1개를 테스트로 보내고,
        # 현재 목록의 기존 공지들은 중복 전송 방지를 위해 기록
        if not seen:
            send_notice(notices[0], webhook)
            seen.update(n["url"] for n in notices)

        else:
            new_notices = [
                n for n in notices
                if n["url"] not in seen
            ]

            # 새 공지가 여러 개면 오래된 것부터 전송
            for notice in reversed(new_notices):
                send_notice(notice, webhook)
                seen.add(notice["url"])

        browser.close()

    save_seen(seen)

import requests

url = "https://forum.kakaogames.com/dokkaebi/"

response = requests.get(
    url,
    headers={
        "User-Agent": "Mozilla/5.0",
        "Referer": "https://www.google.com/",
    },
    timeout=20,
)

print("HTTP 상태 코드:", response.status_code)
print("최종 주소:", response.url)
print("응답 길이:", len(response.text))
print("응답 앞부분:", response.text[:500])

if __name__ == "__main__":
    main()
