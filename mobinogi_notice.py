
def fetch_notices():
    """모비노기 공지 목록을 가져오고, 찾지 못하면 응답 구조를 진단한다."""
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

    print(f"[진단] HTTP 상태 코드: {response.status_code}")
    print(f"[진단] 응답 길이: {len(response.text)}")
    print(f"[진단] 페이지 제목: {soup.title.get_text(strip=True) if soup.title else '(없음)'}")
    print(f"[진단] ul.list 개수: {len(soup.select('ul.list'))}")
    print(f"[진단] li.item 개수: {len(soup.select('li.item'))}")
    print(f"[진단] 공지 링크 개수: {len(soup.select('a[href*=\"/News/Notice/\"]'))}")

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
        # 페이지 전체를 출력하지 않고 구조와 관련된 일부 정보만 로그에 남긴다.
        print("[진단] 공지 목록 선택자로 찾지 못했습니다.")
        print("[진단] 응답 앞부분:")
        print(response.text[:1500])

        raise RuntimeError(
            "공지 목록을 찾지 못했습니다. "
            "위 진단 로그에서 실제 응답 구조를 확인해 주세요."
        )

    print(f"[진단] 공지 {len(notices)}개 발견")
    return notices
