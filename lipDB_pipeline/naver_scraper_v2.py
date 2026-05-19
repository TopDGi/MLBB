"""
네이버 쇼핑 API를 사용한 립스틱 제품 수집
=========================================

네이버 쇼핑 검색 API를 통해 립스틱 제품 정보를 수집.
공식 API 미사용 시 크롤링으로 대체 가능 (headers + delay).

참고:
  - 네이버 검색 API: https://developers.naver.com/docs/serviceapi/search/shopping/shopping.md
  - Client ID / Secret 필요 (환경변수: NAVER_CLIENT_ID, NAVER_CLIENT_SECRET)
"""

import requests
import os
from bs4 import BeautifulSoup
import time
import random
import json


class NaverShoppingAPI:
    """네이버 쇼핑 검색 API 래퍼"""

    BASE_URL = "https://openapi.naver.com/v1/search/shop.json"

    def __init__(self):
        self.client_id = os.environ.get("NAVER_CLIENT_ID")
        self.client_secret = os.environ.get("NAVER_CLIENT_SECRET")

        if not self.client_id or not self.client_secret:
            print("[INFO] Naver API key not found - using crawl mode")
            self.use_api = False
        else:
            self.use_api = True

    def search(self, query="립스틱", display=100, start=1):
        """
        네이버 쇼핑 검색

        Args:
            query: 검색어 (기본값: 립스틱)
            display: 반환 개수 (최대 100)
            start: 시작 위치 (1~)

        Returns:
            [{"title", "link", "image", "brand", "lowestPrice"}, ...]
        """
        if not self.use_api:
            return self._scrape_naver_shopping(query, display, start)

        headers = {
            "X-Naver-Client-Id": self.client_id,
            "X-Naver-Client-Secret": self.client_secret,
        }
        params = {
            "query": query,
            "display": min(display, 100),
            "start": start,
            "sort": "sim",  # 유사도순
        }

        try:
            resp = requests.get(self.BASE_URL, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            products = []
            for item in data.get("items", []):
                products.append({
                    "name": self._clean_html(item["title"]),
                    "brand": "",  # API에서 제공 안 함
                    "img_url": item["image"],
                    "link": item["link"],
                    "price": item.get("lowestPrice", ""),
                })
            return products
        except Exception as e:
            print(f"[ERROR] Naver API error: {e}")
            return []

    def _scrape_naver_shopping(self, query="립스틱", display=100, start=1):
        """
        네이버 쇼핑 크롤링 (API 미사용 시)

        주의: 네이버 약관에 따라 크롤링 가능성 제한
        """
        products = []

        # 네이버 쇼핑 검색 URL (API 없을 때)
        url = f"https://shopping.naver.com/search/all?query={query}&pagingIndex=1"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8",
            "Accept-Language": "ko-KR,ko;q=0.9",
            "Referer": "https://shopping.naver.com/",
        }

        try:
            resp = requests.get(url, headers=headers, timeout=10)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, "html.parser")

            # 네이버 쇼핑 제품 카드 추출 (선택자는 구조 변경 시 업데이트 필요)
            items = soup.select("div.product_item")

            for item in items[:display]:
                name_el = item.select_one("span.product_name")
                img_el = item.select_one("img")
                link_el = item.select_one("a.product_link")
                price_el = item.select_one("span.price_num")

                if not name_el:
                    continue

                img_url = img_el.get("src", "") or img_el.get("data-src", "") if img_el else ""
                link = link_el.get("href", "") if link_el else ""

                if not img_url:
                    continue

                if img_url.startswith("//"):
                    img_url = "https:" + img_url

                if link and not link.startswith("http"):
                    link = "https://shopping.naver.com" + link

                products.append({
                    "name": name_el.get_text(strip=True),
                    "brand": "",
                    "img_url": img_url,
                    "link": link,
                    "price": price_el.get_text(strip=True) if price_el else "",
                })

                time.sleep(random.uniform(0.1, 0.3))  # 과부하 방지

        except Exception as e:
            print(f"[WARNING] Naver Shopping crawl error: {e}")

        return products

    @staticmethod
    def _clean_html(text):
        """HTML 태그 제거"""
        import re
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        return text.strip()

def parse_texture(name: str) -> str:
    name_lower = name.lower()
    if any(k in name for k in ["매트", "matte", "벨벳", "velvet"]):
        return "MATTE"
    elif any(k in name for k in ["글로스", "글로시", "glossy", "gloss", "샤인", "shine"]):
        return "GLOSSY"
    elif any(k in name for k in ["틴트", "tint", "워터"]):
        return "TINT"
    elif any(k in name for k in ["실키", "새틴", "satin", "silky", "크리미", "creamy"]):
        return "SATIN"
    elif any(k in name for k in ["립밤", "밤", "balm"]):
        return "BALM"
    else:
        return "LIPSTICK"
    
    
def scrape_naver_lipsticks(max_items: int = 100) -> list[dict]:
    """
    네이버 쇼핑에서 립스틱 제품 수집

    Args:
        max_items: 수집할 최대 제품 수

    Returns:
        [{"name", "brand", "img_url", "link", "price"}, ...]
    """
    api = NaverShoppingAPI()
    products = []
    seen_names = set()

    SEARCH_QUERIES = [
        "립스틱 코랄 오렌지",        # 봄웜_라이트
        "립스틱 피치 살몬",          # 봄웜_브라이트
        "립스틱 테라코타 브릭",      # 가을웜_뮤트
        "립스틱 버건디 와인 브라운",  # 가을웜_딥
        "립스틱 베이비핑크 로즈핑크", # 여름쿨_라이트
        "립스틱 모브 로즈우드",      # 여름쿨_뮤트
        "립스틱 트루레드 로즈레드",   # 겨울쿨_브라이트
        "립스틱 딥버건디 다크플럼",   # 겨울쿨_딥
    ]

    QUERY_WEIGHTS = {
        "립스틱 코랄 오렌지":        5,   # 봄웜_라이트 이미 45개
        "립스틱 피치 살몬":          15,  # 봄웜_브라이트 4개 → 보충
        "립스틱 테라코타 브릭":      5,   # 가을웜_뮤트 15개
        "립스틱 버건디 와인 브라운":  5,   # 가을웜_딥 6개
        "립스틱 베이비핑크 로즈핑크": 5,   # 여름쿨_라이트 11개
        "립스틱 모브 로즈우드":      15,  # 여름쿨_뮤트 4개 → 보충
        "립스틱 트루레드 로즈레드":   15,  # 겨울쿨_브라이트 0개 → 보충
        "립스틱 딥버건디 다크플럼":   15,  # 겨울쿨_딥 1개 → 보충
    }

    per_query = max(1,max_items // len(SEARCH_QUERIES))

    print(f"[SEARCH] {len(SEARCH_QUERIES)}개 검색어 × {per_query}개 = 목표 {max_items}개...")

    # Page-by-page collection (100 per page)
    for query,count in QUERY_WEIGHTS.items():
        if len(products) >= max_items:
            break

        print(f"  [QUERY] {query}")
        items = api.search(query=query, display=min(count, 100), start=1)

        for item in items:
            if len(products) >= max_items:
                break
            if item["name"] in seen_names:
                continue
            seen_names.add(item["name"])
            products.append({
                "name":    item["name"],
                "brand":   item.get("brand", ""),
                "img_url": item.get("img_url", ""),
                "link":    item.get("link", ""),
                "price":   item.get("price", ""),
                "texture": parse_texture(item["name"]),
            })
            print(f"    [OK] {item['name'][:40]}")

        time.sleep(1.0)

    print(f"[RESULT] {len(products)}개 수집 완료")
    return products
