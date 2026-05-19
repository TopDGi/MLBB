import requests
from bs4 import BeautifulSoup
import time
import random

OLIVEYOUNG_CAT_URL = "https://www.oliveyoung.co.kr/store/display/getMCategoryList.do?dispCatNo=100000100020006"
LIP_CAT_NO = "100000100010013"  # 립 카테고리

# 안티-봇 회피를 위한 현실적인 브라우저 헤더 (Chrome 기준)
def _get_headers():
    user_agents = [
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    ]
    return {
        "User-Agent": random.choice(user_agents),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "Accept-Encoding": "gzip, deflate",  # br 제거 (일부 시스템 호환성)
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7",
        "Connection": "keep-alive",
        "DNT": "1",
        "Cache-Control": "max-age=0",
        "Pragma": "no-cache",
        "Referer": "https://www.oliveyoung.co.kr/",
        "Sec-Ch-Ua": '"Not_A Brand";v="8", "Chromium";v="124", "Google Chrome";v="124"',
        "Sec-Ch-Ua-Mobile": "?0",
        "Sec-Ch-Ua-Platform": '"Windows"',
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": "none",
        "Sec-Fetch-User": "?1",
        "Upgrade-Insecure-Requests": "1",
    }


def scrape_oliveyoung_lips(
    max_pages: int = 5,
    max_items: int | None = None,
    delay: float = 1.5,
) -> list[dict]:
    """
    올리브영 립 카테고리에서 제품 목록을 스크래핑.
    반환: [{"name", "brand", "img_url", "link", "price"}, ...]

    Args:
        max_pages:  최대 페이지 수 (페이지당 약 24~36개)
        max_items:  수집할 최대 제품 수. None이면 max_pages까지 전부 수집.
        delay:      페이지 간 대기 시간(초) — 기본값 1.5s. 올리브영 보호 회피용.

    NOTE: 올리브영 HTML 구조 변경 시 CSS 셀렉터를 조정해야 할 수 있음.
    JS 렌더링이 필요할 경우 Selenium/Playwright로 교체 권장.
    """
    products = []
    seen_names = set()
    session = requests.Session()  # 연결 재사용 (더 브라우저스러움)

    for page in range(1, max_pages + 1):
        params = {"dispCatNo": LIP_CAT_NO, "pageIdx": page}

        # 재시도 로직 (403 에러 대응)
        max_retries = 3
        resp = None
        for attempt in range(max_retries):
            try:
                resp = session.get(
                    OLIVEYOUNG_CAT_URL,
                    params=params,
                    headers=_get_headers(),  # 매 요청마다 새 헤더 생성
                    timeout=15,
                )

                if resp.status_code == 403:
                    raise requests.exceptions.HTTPError(
                        f"403 Forbidden — 올리브영 WAF 차단",
                        response=resp
                    )

                resp.raise_for_status()
                break  # ✅ 성공

            except requests.exceptions.HTTPError as e:
                if "403" in str(e) and attempt < max_retries - 1:
                    wait_time = (2 ** attempt) + random.uniform(0, 1)  # 지수 백오프
                    print(f"  ⏳ 페이지 {page} 403 차단 — {wait_time:.1f}초 후 재시도 ({attempt + 1}/{max_retries})")
                    time.sleep(wait_time)
                    resp = None
                else:
                    print(f"  ❌ 페이지 {page} 요청 실패 (모든 재시도 소진): {e}")
                    resp = None
                    break
            except requests.RequestException as e:
                print(f"  ⚠️ 페이지 {page} 네트워크 오류: {e}")
                resp = None
                break

        if not resp:
            print(f"  ⛔ 페이지 {page}를 얻을 수 없음 — 스크래핑 중단")
            break

        soup = BeautifulSoup(resp.text, "html.parser")

        # 올리브영 상품 카드 셀렉터 (변경될 수 있음)
        cards = (
            soup.select("ul.cate-prd-list > li")
            or soup.select("ul.prd-list > li")
            or soup.select("li.flag-item")
        )

        if not cards:
            print(f"  ℹ️ 페이지 {page}에서 상품을 찾지 못함 — 스크래핑 종료")
            break

        page_count = 0
        for card in cards:
            name_el = card.select_one("p.tx-name") or card.select_one(".prd-name")
            brand_el = card.select_one("p.tx-brand") or card.select_one(".tx-brand")
            price_el = card.select_one("span.tx-cur") or card.select_one(".prd-price .tx-cur")
            img_el = card.select_one("img.prd-img") or card.select_one("img")
            link_el = card.select_one("a.prd-info-area") or card.select_one("a")

            if not name_el:
                continue

            name = name_el.get_text(strip=True)
            if name in seen_names:
                continue
            seen_names.add(name)

            img_url = img_el.get("src", "") or img_el.get("data-src", "") if img_el else ""
            if img_url.startswith("//"):
                img_url = "https:" + img_url

            link = link_el.get("href", "") if link_el else ""
            if link and not link.startswith("http"):
                link = "https://www.oliveyoung.co.kr" + link

            products.append({
                "name": name,
                "brand": brand_el.get_text(strip=True) if brand_el else "",
                "img_url": img_url,
                "link": link,
                "price": price_el.get_text(strip=True) if price_el else "",
            })
            page_count += 1

            if max_items and len(products) >= max_items:
                break  # 목표 개수 도달 시 현재 페이지에서 즉시 중단

        print(f"  📄 페이지 {page}: {page_count}개 수집 (누적 {len(products)}개)")

        if max_items and len(products) >= max_items:
            print(f"  ✔ 목표 {max_items}개 도달 — 스크래핑 종료")
            break

        # 올리브영 반봇 우회: delay ± 랜덤 변동 (0.5~1.0s)
        actual_delay = delay + random.uniform(-0.5, 1.0)
        time.sleep(max(0.5, actual_delay))

    session.close()
    return products
