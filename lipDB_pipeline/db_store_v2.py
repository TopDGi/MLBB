"""
SQLite 캐시 DB 관리
==================
pipeline_cache.db에 스크래핑/색상추출/태깅 중간 결과를 저장.
lipstick_db.json 최종 export 전 단계별 상태 추적용.

tone 체계: 8타입 퍼스널컬러 (matcher.py의 TONE_TYPES와 동일)
  봄웜_라이트, 봄웜_브라이트, 가을웜_뮤트, 가을웜_딥
  여름쿨_라이트, 여름쿨_뮤트, 겨울쿨_브라이트, 겨울쿨_딥
"""

import sqlite3
import json
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "pipeline_cache.db"


def init_db(db_path: Path = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            name             TEXT NOT NULL,
            brand            TEXT DEFAULT '',
            img_url          TEXT DEFAULT '',
            link             TEXT DEFAULT '',
            price            TEXT DEFAULT '',
            texture          TEXT DEFAULT '',
            bgr              TEXT,
            tone             TEXT,
            secondary_tones  TEXT,
            hex              TEXT,
            description      TEXT,
            status           TEXT DEFAULT 'scraped'
        )
    """)
    conn.execute("CREATE UNIQUE INDEX IF NOT EXISTS idx_name ON products(name)")
    conn.commit()
    return conn


def upsert_scraped(conn: sqlite3.Connection, products: list[dict]) -> int:
    """스크래핑 결과 삽입 (이름 기준 중복 무시)."""
    rows = [
        (
            p["name"],
            p.get("brand", ""),
            p.get("img_url", ""),
            p.get("link", ""),
            p.get("price", ""),
            p.get("texture", ""),
        )
        for p in products
    ]
    conn.executemany("""
        INSERT OR IGNORE INTO products (name, brand, img_url, link, price, texture)
        VALUES (?, ?, ?, ?, ?, ?)
    """, rows)
    conn.commit()
    return conn.execute("SELECT changes()").fetchone()[0]


def update_color(conn: sqlite3.Connection, name: str, bgr: list[int]) -> None:
    """BGR 색상 추출 결과 저장."""
    conn.execute(
        "UPDATE products SET bgr=?, status='color_extracted' WHERE name=?",
        (json.dumps(bgr), name),
    )
    conn.commit()


def update_tag(conn: sqlite3.Connection, name: str, tag: dict) -> None:
    """color_analyzer 태깅 결과 저장."""
    conn.execute("""
        UPDATE products
        SET tone=?, secondary_tones=?, hex=?, description=?, status='done'
        WHERE name=?
    """, (
        tag.get("recommended_for", ""),
        json.dumps(tag.get("secondary_tones", []), ensure_ascii=False),
        tag.get("hex", ""),
        tag.get("description", ""),
        name,
    ))
    conn.commit()


def get_pending_color(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """BGR이 아직 없는 제품의 (name, img_url) 반환."""
    return conn.execute(
        "SELECT name, img_url FROM products WHERE bgr IS NULL AND img_url != ''"
    ).fetchall()


def get_pending_tag(conn: sqlite3.Connection) -> list[tuple[str, str]]:
    """BGR은 있지만 태깅이 안 된 제품의 (name, bgr) 반환."""
    return conn.execute(
        "SELECT name, bgr FROM products WHERE bgr IS NOT NULL AND tone IS NULL"
    ).fetchall()


def get_all_done(conn: sqlite3.Connection) -> list[dict]:
    """완료된 제품 전체를 dict 리스트로 반환 (export_json용)."""
    rows = conn.execute("""
        SELECT name, brand, tone, secondary_tones, bgr, hex, link, img_url, description, texture
        FROM products
        WHERE status = 'done'
    """).fetchall()

    result = []
    for row in rows:
        name, brand, tone, secondary_tones, bgr, hex_val, link, img_url, description, texture = row
        result.append({
            "name":            name,
            "brand":           brand,
            "tone":            tone,
            "secondary_tones": json.loads(secondary_tones) if secondary_tones else [],
            "bgr":             json.loads(bgr) if bgr else [],
            "hex":             hex_val or "",
            "link":            link,
            "img_url":         img_url,
            "description":     description or "",
            "texture":         texture or "",
        })
    return result


def get_stats(conn: sqlite3.Connection) -> dict:
    """파이프라인 진행 현황 통계."""
    row = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN status='scraped'          THEN 1 ELSE 0 END) as scraped,
            SUM(CASE WHEN status='color_extracted'  THEN 1 ELSE 0 END) as color_only,
            SUM(CASE WHEN status='done'             THEN 1 ELSE 0 END) as done
        FROM products
    """).fetchone()
    return {
        "total":      row[0],
        "scraped":    row[1],
        "color_only": row[2],
        "done":       row[3],
    }