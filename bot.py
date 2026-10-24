
import json
import os
from pathlib import Path
from urllib.parse import urljoin, urldefrag

import requests
from bs4 import BeautifulSoup

STATE_FILE = Path("seen_posts.json")

# 마비노기 모바일 공식 공지사항 탭
MABI_NOTICE_URL = "https://mabinogimobile.nexon.com/News/Notice"

# 도깨비의 세계 공식 커뮤니티 공지사항 탭
DOKKAEBI_NOTICE_URL = "https://forum.kakaogames.com/dokkaebi/postList/?code=notice"

HEADERS = {
    "User-Agent": "Mozilla/5.0 (compatible; GameNoticeBot/1.0)"
}


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


def get_soup(url):
    response = requests.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")


def get_mabi_posts():
    soup = get_soup(MABI_NOTICE_URL)
    posts = []
    found = set()

    for a in soup.select("a[href]"):
        title = a.get_text(" ", strip=True)
        link = urldefrag(urljoin(MABI_NOTICE_URL, a["href"]))[0]

        if not title:
            continue

        if "/News/Notice/" not in link:
            continue

        if link in found:
            continue

        found.add(link)
        posts.append({
            "game": "마비노기 모바일",
            "title": title,
            "url": link,
        })

    return posts


def get_dokkaebi_posts():
    soup = get_soup(DOKKAEBI_NOTICE_URL)
    posts = []
    found = set()

    for a in soup.select("a[href]"):
        title = a.get_text(" ", strip=True)
        link = urldefrag(urljoin(DOKKAEBI_NOTICE_URL, a["href"]))[0]

        if not title:
            continue

        if "/dokkaebi/postView/" not in link:
            continue

        if "code=notice" not in link:
            continue

        if link in found:
            continue

        found.add(link)
        posts.append({
            "game": "도깨비의 세계",
            "title": title,
            "url": link,
        })

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


def main():
    seen = load_seen()
    first_run = not seen

    targets = [
        ("MABI_WEBHOOK", get_mabi_posts),
        ("DOKKAEBI_WEBHOOK", get_dokkaebi_posts),
    ]

    for secret_name, fetch_posts in targets:
        webhook = os.getenv(secret_name)

        if not webhook:
            raise RuntimeError(
                f"GitHub Secrets에 {secret_name} 설정이 필요합니다."
            )

        posts = fetch_posts()
        print(f"{secret_name}: 게시글 {len(posts)}개 확인")

        if first_run:
            for post in posts:
                seen.add(post["url"])
            continue

        new_posts = [
            post for post in posts
            if post["url"] not in seen
        ]

        for post in reversed(new_posts):
            send_notice(post, webhook)
            seen.add(post["url"])
            print(f"전송 완료: {post['title']}")

    save_seen(seen)


if __name__ == "__main__":
    main()
