"""
네이버 쇼핑 기반 립스틱 DB 구축 (v2)
=====================================
실행: python build_db_from_naver_v2.py [--items N]

단계:
  1. 네이버 쇼핑에서 립스틱 제품 검색 (8타입 검색어)
  2. SQLite에 수집 결과 저장 (중간 캐시)
  3. 각 제품 이미지 다운로드 → BGR 추출 → SQLite 업데이트
  4. color_analyzer_v2로 퍼스널컬러 타입 태깅 → SQLite 업데이트
  5. SQLite → lipstick_db.json export

중간에 끊겨도 SQLite 캐시 덕분에 이어서 재개 가능.
재실행 시 이미 완료된 단계는 건너뜀.

네이버 API 설정:
  .env 파일에 추가:
    NAVER_CLIENT_ID=your_client_id
    NAVER_CLIENT_SECRET=your_client_secret
"""

import os
import sys
import time
import json
from pathlib import Path

try:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).parent / ".env")
except ImportError:
    pass

import requests

from lipDB_pipeline.naver_scraper_v2 import scrape_naver_lipsticks
from lipDB_pipeline.color_extractor import extract_center_bgr
from lipDB_pipeline.color_analyzer_v2 import analyze_lipstick_color
from lipDB_pipeline.db_store_v2 import (
    init_db,
    upsert_scraped,
    update_color,
    update_tag,
    get_pending_color,
    get_pending_tag,
    get_all_done,
    get_stats,
)

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Referer": "https://shopping.naver.com/",   # ← 추가: 이게 없으면 CDN이 이미지 차단
    "Accept": "image/webp,image/apng,image/*,*/*;q=0.8",
}


def step1_search(conn, max_items: int) -> None:
    """네이버 쇼핑 검색 → SQLite 저장"""
    print(f"\n[STEP 1] 네이버 쇼핑 검색 ({max_items}개 목표)...")

    products = scrape_naver_lipsticks(max_items=max_items)
    if not products:
        print("  [ERROR] 검색 결과 없음")
        sys.exit(1)

    inserted = upsert_scraped(conn, products)
    print(f"  [OK] {len(products)}개 수집 → {inserted}개 신규 저장 (중복 제외)")


def step2_color(conn) -> None:
    """이미지 URL → BGR 추출 → SQLite 업데이트"""
    pending = get_pending_color(conn)
    if not pending:
        print("\n[STEP 2] BGR 추출: 건너뜀 (모두 완료됨)")
        return
 
    print(f"\n[STEP 2] BGR 색상 추출 ({len(pending)}개)...")
    fail_count = 0
 
    for i, (name, img_url) in enumerate(pending, 1):
        try:
            # ── 수정: 재시도 로직 추가 (최대 2회) ──────────────────────────
            bgr = None
            for attempt in range(2):
                try:
                    resp = requests.get(img_url, headers=HEADERS, timeout=15)
                    resp.raise_for_status()
                    bgr = extract_center_bgr(resp.content)
                    if bgr:
                        break
                except Exception:
                    time.sleep(1.0)
                    continue
 
            if bgr:
                update_color(conn, name, bgr)
                print(f"  [OK] [{i:>3}/{len(pending)}] BGR {bgr}  {name[:35]}")
            else:
                fail_count += 1
                print(f"  [FAIL] [{i:>3}/{len(pending)}] 이미지 디코드 실패  {name[:35]}")
        except Exception as e:
            fail_count += 1
            print(f"  [ERROR] [{i:>3}/{len(pending)}] {e}  {name[:35]}")
        time.sleep(0.3)
 
    success = len(pending) - fail_count
    print(f"  [DONE] {success}/{len(pending)}개 BGR 추출 완료 (실패: {fail_count}개)")


def step3_tag(conn) -> None:
    """BGR → 퍼스널컬러 타입 태깅 → SQLite 업데이트"""
    pending = get_pending_tag(conn)
    if not pending:
        print("\n[STEP 3] 톤 태깅: 건너뜀 (모두 완료됨)")
        return

    print(f"\n[STEP 3] 퍼스널컬러 타입 태깅 ({len(pending)}개)...")
    for i, (name, bgr_json) in enumerate(pending, 1):
        try:
            bgr = json.loads(bgr_json)
            tag = analyze_lipstick_color(bgr)
            update_tag(conn, name, tag)
            print(
                f"  [OK] [{i:>3}/{len(pending)}] "
                f"{tag['recommended_for']:<12} "
                f"(차선: {str(tag['secondary_tones']):<30}) "
                f"{name[:25]}"
            )
        except Exception as e:
            print(f"  [ERROR] [{i:>3}/{len(pending)}] {e}  {name[:35]}")


def step4_export(conn, out_path: str = "lipstick_db.json") -> int:
    """SQLite 완료 항목 → lipstick_db.json export"""
    print(f"\n[STEP 4] {out_path} 생성 중...")

    entries = get_all_done(conn)
    if not entries:
        print("  [ERROR] 완료된 항목이 없습니다. 이전 단계를 확인하세요.")
        return 0

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(entries, f, ensure_ascii=False, indent=4)

    print(f"  [DONE] {len(entries)}개 → {out_path}")
    return len(entries)


def run(max_items: int = 20, out_path: str = "lipstick_db.json") -> None:
    # SQLite 초기화 (이미 있으면 기존 캐시 유지)
    conn = init_db()

    # 진행 현황 출력
    stats = get_stats(conn)
    if stats["total"] > 0:
        print(f"\n[캐시 현황] 전체 {stats['total']}개 | "
              f"수집완료 {stats['scraped']}개 | "
              f"BGR완료 {stats['color_only']}개 | "
              f"태깅완료 {stats['done']}개")

    step1_search(conn, max_items)
    step2_color(conn)
    step3_tag(conn)
    count = step4_export(conn, out_path)

    conn.close()

    print(f"\n{'='*55}")
    if count > 0:
        print(f"[SUCCESS] 파이프라인 완료!")
        print(f"  생성 파일 : {out_path} ({count}개)")
        print(f"  다음 단계 : python run_pipeline.py 로 추천 테스트")
    else:
        print(f"[FAIL] lipstick_db.json 생성 실패. 로그를 확인하세요.")


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(
        description="네이버 쇼핑 기반 립스틱 DB 구축 v2",
        epilog="""
사용 예시:
  python build_db_from_naver_v2.py             # 기본 (20개)
  python build_db_from_naver_v2.py --items 80  # 80개 수집
        """
    )
    parser.add_argument("--items", type=int, default=20, help="수집할 제품 수 (기본값: 20)")
    parser.add_argument("--out", type=str, default="lipstick_db.json", help="출력 파일명")
    args = parser.parse_args()
    run(max_items=args.items, out_path=args.out)