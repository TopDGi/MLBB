"""
네이버 쇼핑 API를 사용한 립스틱 제품 수집
=========================================
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
            "sort": "sim",
        }

        try:
            resp = requests.get(self.BASE_URL, headers=headers, params=params, timeout=10)
            resp.raise_for_status()
            data = resp.json()

            products = []
            for item in data.get("items", []):
                products.append({
                    "name": self._clean_html(item["title"]),
                    "brand": "",
                    "img_url": item["image"],
                    "link": item["link"],
                    "price": item.get("lowestPrice", ""),
                })
            return products
        except Exception as e:
            print(f"[ERROR] Naver API error: {e}")
            return []

    def _scrape_naver_shopping(self, query="립스틱", display=100, start=1):
        products = []
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
                time.sleep(random.uniform(0.1, 0.3))
        except Exception as e:
            print(f"[WARNING] Naver Shopping crawl error: {e}")
        return products

    @staticmethod
    def _clean_html(text):
        import re
        text = re.sub(r"<[^>]+>", "", text)
        text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
        return text.strip()


def parse_texture(name: str) -> str:
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


# ── 수정 1: 검색어 대폭 확장 (8개 → 40개) ──────────────────────────────────
# 톤별로 5개씩 검색어를 두어 다양한 제품이 수집되도록 함
SEARCH_QUERIES_BY_TONE = {
    "봄웜_라이트": [
        "립스틱 코랄 오렌지",
        "립스틱 피치 오렌지 봄웜",
        "립스틱 살몬 코랄",
        "오렌지 립스틱 발색",
        "코랄 립틴트 봄",
    ],
    "봄웜_브라이트": [
        "립스틱 피치 살몬",
        "립스틱 피치핑크 브라이트",
        "살몬핑크 립스틱",
        "립스틱 피치 브라이트 봄",
        "피치 립틴트 발색",
    ],
    "가을웜_뮤트": [
        "립스틱 테라코타 브릭",
        "립스틱 브릭레드 가을",
        "테라코타 립메이크업",
        "립스틱 뮤트 웜톤",
        "립스틱 어스톤 갈웜",
    ],
    "가을웜_딥": [
        "립스틱 버건디 와인 브라운",
        "립스틱 딥브라운 가을웜",
        "와인레드 립스틱",
        "립스틱 다크브라운 웜",
        "버건디 립메이크업 가을",
    ],
    "여름쿨_라이트": [
        "립스틱 베이비핑크 로즈핑크",
        "립스틱 쿨톤 연핑크",
        "베이비핑크 립틴트",
        "립스틱 라이트 핑크 여름쿨",
        "핑크 립스틱 밝은 쿨톤",
    ],
    "여름쿨_뮤트": [
        "립스틱 모브 로즈우드",
        "립스틱 모브핑크 뮤트",
        "로즈우드 립메이크업",
        "립스틱 더스티핑크 쿨",
        "모브 립스틱 여름쿨",
    ],
    "겨울쿨_브라이트": [
        "립스틱 트루레드 로즈레드",
        "립스틱 레드 쿨톤 겨울",
        "블루베이스 레드 립스틱",
        "립스틱 선명한 레드 쿨",
        "레드 립메이크업 겨울쿨",
    ],
    "겨울쿨_딥": [
        "립스틱 딥버건디 다크플럼",
        "립스틱 다크플럼 겨울",
        "딥 버건디 립메이크업",
        "립스틱 다크레드 쿨톤",
        "플럼 립스틱 겨울쿨 딥",
    ],
}


def scrape_naver_lipsticks(max_items: int = 100) -> list[dict]:
    """
    네이버 쇼핑에서 립스틱 제품 수집 (톤별 균형 수집)

    Args:
        max_items: 수집할 최대 제품 수

    Returns:
        [{"name", "brand", "img_url", "link", "price", "texture"}, ...]
    """
    api = NaverShoppingAPI()
    products = []
    seen_names = set()

    num_tones = len(SEARCH_QUERIES_BY_TONE)           # 8
    per_tone = max(1, max_items // num_tones)          # 톤당 목표 개수
    all_queries = []
    for tone, queries in SEARCH_QUERIES_BY_TONE.items():
        per_query = max(1, per_tone // len(queries))   # 검색어당 요청 개수
        for q in queries:
            all_queries.append((q, per_query))

    total_queries = len(all_queries)
    print(f"[SEARCH] {total_queries}개 검색어, 톤당 {per_tone}개 목표 = 총 {max_items}개...")

    for query, display_count in all_queries:
        if len(products) >= max_items:
            break

        print(f"  [QUERY] {query}")

        # ── 수정 2: 페이지네이션으로 더 많은 결과 수집 ──────────────────────
        # Naver API는 한 번에 최대 100개, start로 페이지 이동 가능
        collected_this_query = 0
        start = 1
        while collected_this_query < display_count and len(products) < max_items:
            batch = min(100, display_count - collected_this_query)
            items = api.search(query=query, display=batch, start=start)
            if not items:
                break
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
                collected_this_query += 1
                print(f"    [OK] {item['name'][:40]}")
            start += batch
            if len(items) < batch:  # 더 이상 결과 없음
                break
            time.sleep(0.5)

        time.sleep(1.0)

    print(f"[RESULT] {len(products)}개 수집 완료")
    return products