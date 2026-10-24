
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urldefrag

from playwright.sync_api import sync_playwright

STATE_FILE = Path("seen_posts.json")

MABI_URL = "https://mabinogimobile.nexon.com/News/Notice"
DOKKAEBI_URL = "https://bbs.kakaogames.com/ko/1329429/notice"

def load_seen():
    if not STATE_FILE.exists():
        return set()
    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        return set(data) if isinstance(data, list) else set()
    except (json.JSONDecodeError, OSError):
        return set()

def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

def get_posts(page, url, game):
    print(f"\n[{game}] 페이지 접속: {url}")
    try:
        page.goto(url, wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(7000)
    except Exception as exc:
        print(f"[{game}] 페이지 로딩 오류: {exc}")
        return []

    print(f"[{game}] 최종 주소: {page.url}")
    print(f"[{game}] 페이지 제목: {page.title()}")

    try:
        page_text = page.locator("body").inner_text(timeout=15000)
        print(f"[{game}] 페이지 글자 수: {len(page_text)}")
        print(f"[{game}] 화면 텍스트 앞부분: {page_text[:500]!r}")
    except Exception as exc:
        print(f"[{game}] 화면 텍스트 읽기 오류: {exc}")

    posts = []
    found = set()

    for a in page.locator("a[href]").all():
        try:
            href = a.get_attribute("href")
            title = a.inner_text().strip()
            if not href or not title:
                continue

            link = urldefrag(urljoin(page.url, href))[0]
            low = link.lower()

            if game == "마비노기 모바일":
                if not re.search(r"/news/notice/\d+", low):
                    continue
            else:
                if "/ko/1329429/notice/detail" not in low:
                    continue

            if link in found:
                continue

            found.add(link)
            posts.append({
                "game": game,
                "title": title,
                "url": link,
            })
        except Exception:
            continue

    print(f"[{game}] 공지 게시글 {len(posts)}개 발견")
    for post in posts[:5]:
        print(f"  - {post['title']} | {post['url']}")

    return posts

def send_notice(post, webhook):
    message = (
        f"📢 **[{post['game']} 공지사항]**\n"
        f"{post['title']}\n"
        f"{post['url']}"
    )
    from requests import post as http_post
    response = http_post(
        webhook,
        json={
            "content": message,
            "allowed_mentions": {"parse": []},
        },
        timeout=20,
    )
    response.raise_for_status()
    print(f"디스코드 전송 성공: {post['title']}")

def main():
    seen = load_seen()

    targets = [
        ("MABI_WEBHOOK", MABI_URL, "마비노기 모바일"),
        ("DOKKAEBI_WEBHOOK", DOKKAEBI_URL, "도깨비의 세계"),
    ]

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        page = browser.new_page(locale="ko-KR")

        for secret_name, url, game in targets:
            webhook = os.getenv(secret_name)
            if not webhook:
                raise RuntimeError(
                    f"GitHub Secrets 설정 누락: {secret_name}"
                )

            posts = get_posts(page, url, game)
            if not posts:
                print(f"[{game}] 게시글을 찾지 못해 전송하지 않습니다.")
                continue

            if not seen:
                # 첫 실행에서는 기존 공지를 전부 기록하고,
                # 테스트용으로 가장 위의 공지 1개만 전송
                for post in posts:
                    seen.add(post["url"])
                send_notice(posts[0], webhook)
                continue

            new_posts = [post for post in posts if post["url"] not in seen]
            for post in reversed(new_posts):
                send_notice(post, webhook)
                seen.add(post["url"])

        browser.close()

    save_seen(seen)

if __name__ == "__main__":
    main()
