
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin, urldefrag

import requests
from bs4 import BeautifulSoup

STATE_FILE = Path("seen_posts.json")

MABI_NOTICE_URL = "https://mabinogimobile.nexon.com/News/Notice"
DOKKAEBI_NOTICE_URL = "https://bbs.kakaogames.com/ko/1329429/notice"

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/130.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
}

TEST_MODE = True



def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=30)
    print(f"페이지 요청: {url}")
    print(f"HTTP 상태 코드: {response.status_code}")
    print(f"최종 접속 주소: {response.url}")
    print(f"HTML 길이: {len(response.text)}")
    print(f"HTML 앞부분: {response.text[:500]!r}")

    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")



def load_seen():
    if not STATE_FILE.exists():
        return set()

    try:
        data = json.loads(STATE_FILE.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return set(data)
    except (json.JSONDecodeError, OSError):
        pass

    return set()


def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def extract_title(a):
    title = a.get_text(" ", strip=True)
    if title:
        return title

    img = a.find("img")
    if img:
        return img.get("alt", "").strip()

    return ""


def get_mabi_posts():
    soup = get_soup(MABI_NOTICE_URL)
    posts = []
    found = set()

    for a in soup.select("a[href]"):
        link = urldefrag(urljoin(MABI_NOTICE_URL, a["href"]))[0]
        path = link.lower().split("?")[0]

        # 공지사항 상세 주소만 허용
        if not re.search(r"/news/notice/\d+", path):
            continue

        title = extract_title(a)
        if not title or link in found:
            continue

        found.add(link)
        posts.append({
            "game": "마비노기 모바일",
            "title": title,
            "url": link,
        })

    print(f"마비노기 모바일: 공지 {len(posts)}개 수집")
    for post in posts[:3]:
        print("수집 확인:", post["title"], post["url"])

    return posts


def get_dokkaebi_posts():
    soup = get_soup(DOKKAEBI_NOTICE_URL)
    posts = []
    found = set()

    for a in soup.select("a[href]"):
        link = urldefrag(urljoin(DOKKAEBI_NOTICE_URL, a["href"]))[0]
        path = link.split("?")[0].rstrip("/")

        # 새 공식 게시판의 공지 상세 주소
        if not re.search(r"/ko/1329429/notice/detail$", path):
            continue

        title = extract_title(a)
        if not title or link in found:
            continue

        found.add(link)
        posts.append({
            "game": "도깨비의 세계",
            "title": title,
            "url": link,
        })

    print(f"도깨비의 세계: 공지 {len(posts)}개 수집")
    for post in posts[:3]:
        print("수집 확인:", post["title"], post["url"])

    return posts


def send_notice(post, webhook):
    message = (
        f"📢 **[{post['game']} 공지사항]**\n"
        f"{post['title']}\n"
        f"{post['url']}"
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
    print(f"디스코드 전송 성공: {post['title']}")


def main():
    seen = load_seen()

    targets = [
        ("MABI_WEBHOOK", get_mabi_posts),
        ("DOKKAEBI_WEBHOOK", get_dokkaebi_posts),
    ]

    for secret_name, fetch_posts in targets:
        webhook = os.getenv(secret_name)
        if not webhook:
            raise RuntimeError(
                f"GitHub Secrets 설정 누락: {secret_name}"
            )

        try:
            posts = fetch_posts()
        except Exception as exc:
            print(f"{secret_name} 수집 실패: {type(exc).__name__}: {exc}")
            continue

        if not posts:
            print(
                f"{secret_name}: 게시글 0개. "
                "사이트의 HTML 구조 또는 접근 방식을 확인해야 합니다."
            )
            continue

        if TEST_MODE:
            # 테스트 중에는 게임별로 기존 공지 하나를 전송
            send_notice(posts[0], webhook)
            continue

        new_posts = [p for p in posts if p["url"] not in seen]

        for post in reversed(new_posts):
            send_notice(post, webhook)
            seen.add(post["url"])

    save_seen(seen)


if __name__ == "__main__":
    main()
