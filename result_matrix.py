"""
top-4 추천 결과 → 2×2 매트릭스 이미지 합성
============================================

구조:
┌─────────────────┬─────────────────┐
│  1위            │  2위            │
│  [립 적용 사진] │  [립 적용 사진] │
│  제품명 / 점수  │  제품명 / 점수  │
├─────────────────┼─────────────────┤
│  3위            │  4위            │
│  [립 적용 사진] │  [립 적용 사진] │
│  제품명 / 점수  │  제품명 / 점수  │
└─────────────────┴─────────────────┘
        상단: 퍼스널 톤 / 어울리는 립 색상 힌트
"""

import os
import cv2
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from typing import Optional


# ── 레이아웃 상수 ──────────────────────────────
CELL_W   = 400
CELL_H   = 460
HEADER_H = 80
LABEL_H  = 65
IMG_H    = CELL_H - LABEL_H
MATRIX_W = CELL_W * 2
MATRIX_H = HEADER_H + CELL_H * 2

# ── 컬러 팔레트 (RGB — PIL 기준) ───────────────
BG_COLOR       = (245, 242, 240)
HEADER_COLOR   = (60,  45,  40)
RANK1_BORDER   = (180, 130, 100)
DEFAULT_BORDER = (200, 190, 185)
TEXT_WHITE     = (255, 255, 255)
TEXT_DARK      = (50,  40,  35)
TEXT_MUTED     = (140, 128, 122)
SCORE_COLOR    = (80,  150, 90)


# ── 폰트 로드 ──────────────────────────────────
def _find_korean_font() -> str:
    """시스템에서 한글 지원 폰트 경로 탐색"""
    candidates = [
        # Windows
        "C:/Windows/Fonts/malgun.ttf",
        "C:/Windows/Fonts/malgunbd.ttf",
        "C:/Windows/Fonts/gulim.ttc",
        "C:/Windows/Fonts/batang.ttc",
        # macOS
        "/System/Library/Fonts/AppleSDGothicNeo.ttc",
        "/Library/Fonts/AppleGothic.ttf",
        # Linux
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/opentype/nanum/NanumGothic.ttf",
    ]
    for path in candidates:
        if os.path.exists(path):
            return path
    return ""


_FONT_PATH = _find_korean_font()


def _font(size: int) -> ImageFont.FreeTypeFont:
    if _FONT_PATH:
        try:
            return ImageFont.truetype(_FONT_PATH, size)
        except Exception:
            pass
    return ImageFont.load_default()


# ── 유틸 ───────────────────────────────────────
def _cv2_to_pil(img: np.ndarray) -> Image.Image:
    return Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))


def _pil_to_cv2(img: Image.Image) -> np.ndarray:
    return cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)


def _fit_image(img: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
    h, w = img.shape[:2]
    scale = max(target_w / w, target_h / h)
    new_w, new_h = int(w * scale), int(h * scale)
    resized = cv2.resize(img, (new_w, new_h), interpolation=cv2.INTER_AREA)
    x = (new_w - target_w) // 2
    y = (new_h - target_h) // 2
    return resized[y:y + target_h, x:x + target_w]


def _truncate(text: str, max_len: int = 22) -> str:
    return text if len(text) <= max_len else text[:max_len - 1] + "…"


def _hex_to_rgb(hex_str: str) -> Optional[tuple]:
    try:
        h = hex_str.lstrip("#")
        return tuple(int(h[i:i+2], 16) for i in (0, 2, 4))
    except Exception:
        return None


# ── 헤더 ───────────────────────────────────────
def _draw_header(canvas_cv2: np.ndarray, tone: str, hint: str) -> None:
    region = canvas_cv2[0:HEADER_H, 0:MATRIX_W].copy()
    pil    = _cv2_to_pil(region)
    draw   = ImageDraw.Draw(pil)

    draw.rectangle([(0, 0), (MATRIX_W, HEADER_H)], fill=HEADER_COLOR)
    draw.text((20, 12), f"Personal Color : {tone}",
              font=_font(20), fill=TEXT_WHITE)
    draw.text((20, 46), f"Recommended    : {hint}",
              font=_font(15), fill=(200, 185, 175))

    canvas_cv2[0:HEADER_H, 0:MATRIX_W] = _pil_to_cv2(pil)


# ── 셀 ─────────────────────────────────────────
def _draw_cell(
    canvas_cv2: np.ndarray,
    image_path: str,
    item: dict,
    col: int,
    row: int,
    visualizer,
    landmarks,
) -> None:
    x0 = col * CELL_W
    y0 = HEADER_H + row * CELL_H

    rank  = item["rank"]
    bgr   = item["bgr"]
    name  = _truncate(item.get("name", ""), 20)
    brand = _truncate(item.get("brand", ""), 16)
    score = item.get("score", 0)
    hex_  = item.get("hex", "")

    # 립스틱 적용 이미지 (image_path str을 그대로 전달)
    try:
        texture_map = {"MATTE": "matte", "GLOSSY": "glossy", "TINT": "tint", "SATIN": "matte", "BALM": "glossy", "LIPSTICK": "tint"}
        texture_str = texture_map.get(item.get("texture", ""), "matte")
        lip_img, _ = visualizer.apply_lipstick(image_path, landmarks, bgr, intensity=0.55, texture=texture_str)
        if lip_img is None:
            raise ValueError
    except Exception as e:
        print(f"    ⚠️  {rank}위 렌더링 실패: {e}, 원본 이미지 사용")
        lip_img = cv2.imread(image_path)

    # 사진 삽입
    cell_img = _fit_image(lip_img, CELL_W, IMG_H)
    canvas_cv2[y0:y0 + IMG_H, x0:x0 + CELL_W] = cell_img

    # 테두리 (cv2)
    border_bgr = (100, 130, 180) if rank == 1 else (185, 190, 200)
    thickness  = 3 if rank == 1 else 1
    cv2.rectangle(canvas_cv2, (x0, y0), (x0 + CELL_W, y0 + IMG_H), border_bgr, thickness)

    # 라벨 영역 → PIL 렌더링
    label_y = y0 + IMG_H
    region  = canvas_cv2[label_y:label_y + LABEL_H, x0:x0 + CELL_W].copy()
    pil     = _cv2_to_pil(region)
    draw    = ImageDraw.Draw(pil)

    draw.rectangle([(0, 0), (CELL_W, LABEL_H)], fill=BG_COLOR)
    draw.line([(0, 0), (CELL_W, 0)], fill=DEFAULT_BORDER, width=1)

    # 랭크 배지
    badge_color = RANK1_BORDER if rank == 1 else DEFAULT_BORDER
    draw.ellipse([(6, 6), (34, 34)], fill=badge_color)
    draw.text((14, 9), str(rank), font=_font(14), fill=TEXT_WHITE)

    # 브랜드
    draw.text((42, 5),  brand,          font=_font(12), fill=TEXT_MUTED)
    # 제품명
    draw.text((42, 22), name,           font=_font(14), fill=TEXT_DARK)
    # 점수
    draw.text((42, 45), f"{score:.1f}pt", font=_font(12), fill=SCORE_COLOR)

    # 색상 스와치
    rgb = _hex_to_rgb(hex_) if hex_ else None
    if rgb:
        sx = CELL_W - 34
        draw.rectangle([(sx, 8), (sx + 24, 32)], fill=rgb, outline=DEFAULT_BORDER)

    canvas_cv2[label_y:label_y + LABEL_H, x0:x0 + CELL_W] = _pil_to_cv2(pil)


# ── 메인 ───────────────────────────────────────
def build_matrix(
    image_path: str,
    analysis_result: dict,
    top4_result: dict,
    visualizer,
    output_path: Optional[str] = None,
    image_array: Optional[np.ndarray] = None,
) -> np.ndarray:
    """
    top-4 결과 → 2×2 매트릭스 이미지 생성

    Args:
        image_path:      원본 얼굴 이미지 경로
        analysis_result: harmony_analyzer.analyze() 결과
        top4_result:     matcher.get_top4() 결과
        visualizer:      LipVisualizer_v2 인스턴스
        output_path:     저장 경로 (None이면 저장 안 함)

    Returns:
        합성된 매트릭스 이미지 (numpy array)
    """
    landmarks = analysis_result["raw_landmarks"]
    top4      = top4_result.get("top4", [])
    tone      = top4_result.get("user_diagnosed_tone", "")
    hint      = top4_result.get("tone_lip_hint", "")

    # 캔버스
    bg_bgr = (BG_COLOR[2], BG_COLOR[1], BG_COLOR[0])
    canvas = np.full((MATRIX_H, MATRIX_W, 3), bg_bgr, dtype=np.uint8)

    # 헤더
    _draw_header(canvas, tone, hint)

    # 4개 셀
    positions = [(0, 0), (1, 0), (0, 1), (1, 1)]
    for i, item in enumerate(top4[:4]):
        col, row = positions[i]
        _draw_cell(canvas, image_path, item, col, row, visualizer, landmarks)

    # 구분선
    border_bgr = (DEFAULT_BORDER[2], DEFAULT_BORDER[1], DEFAULT_BORDER[0])
    cv2.line(canvas, (MATRIX_W // 2, HEADER_H), (MATRIX_W // 2, MATRIX_H), border_bgr, 1)
    cv2.line(canvas, (0, HEADER_H + CELL_H), (MATRIX_W, HEADER_H + CELL_H), border_bgr, 1)

    if output_path:
        cv2.imwrite(output_path, canvas)
        print(f"  [매트릭스] 저장 완료: {output_path}")

    return canvas