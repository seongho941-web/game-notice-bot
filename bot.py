
import json
import os
import re
from pathlib import Path
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

STATE_FILE = Path("seen_posts.json")

MABI_PAGES = {
    "공지사항": "https://mabinogimobile.nexon.com/News/Notice",
    "업데이트": "https://mabinogimobile.nexon.com/News/Update",
    "이벤트": "https://mabinogimobile.nexon.com/News/Events",
}

DOKKAEBI_NOTICES = "https://forum.kakaogames.com/dokkaebi/postList/?code=notice"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GameNoticeBot/1.0)"
}


def load_seen():
    if not STATE_FILE.exists():
        return set()

    try:
        return set(json.loads(STATE_FILE.read_text(encoding="utf-8")))
    except (json.JSONDecodeError, OSError):
        return set()


def save_seen(seen):
    STATE_FILE.write_text(
        json.dumps(sorted(seen), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_mabi_posts():
    posts = []

    for category, page_url in MABI_PAGES.items():
        soup = get_soup(page_url)

        for a in soup.select("a[href]"):
            title = a.get_text(" ", strip=True)
            link = urljoin(page_url, a.get("href", ""))

            if not title:
                continue

            if not re.search(r"/News/(Notice|Update|Events)/\d+", link):
                continue

            if any(p["url"] == link for p in posts):
                continue

            posts.append({
                "game": "마비노기 모바일",
                "category": category,
                "title": title,
                "url": link,
            })

    return posts


def get_dokkaebi_posts():
    soup = get_soup(DOKKAEBI_NOTICES)
    posts = []

    for a in soup.select("a[href]"):
        title = a.get_text(" ", strip=True)
        link = urljoin(DOKKAEBI_NOTICES, a.get("href", ""))

        if not title:
            continue

        if "/dokkaebi/postView/" not in link:
            continue

        if "code=notice" not in link:
            continue

        posts.append({
            "game": "도깨비의세계",
            "category": "공지사항",
            "title": title,
            "url": link,
        })

    return posts


def send_notice(post, webhook):
    message = (
        f"📢 **[{post['game']} · {post['category']}]**\n"
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


def main():
    seen = load_seen()

    targets = [
        ("MABI_WEBHOOK", get_mabi_posts),
        ("DOKKAEBI_WEBHOOK", get_dokkaebi_posts),
    ]

    for secret_name, fetch_posts in targets:
        webhook = os.getenv(secret_name)

        if not webhook:
            raise RuntimeError(f"GitHub Secret 설정 누락: {secret_name}")

        posts = fetch_posts()
        print(f"{secret_name}: 게시글 {len(posts)}개 확인")

        # 첫 실행에서는 기존 글을 기록만 하고 과거 공지를 몰아서 보내지 않음
        if not seen:
            for post in posts:
                seen.add(post["url"])
            continue

        new_posts = [post for post in posts if post["url"] not in seen]

        for post in reversed(new_posts):
            send_notice(post, webhook)
            seen.add(post["url"])
            print(f"전송 완료: {post['title']}")

    save_seen(seen)


if __name__ == "__main__":
    main()
