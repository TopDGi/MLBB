"""
립스틱 색상 분석 → 어울리는 퍼스널컬러 타입 태깅
==================================================

핵심 개념 정리:
- 퍼스널 톤(사람): 봄웜_라이트, 봄웜_브라이트, 가을웜_뮤트, 가을웜_딥
                   여름쿨_라이트, 여름쿨_뮤트, 겨울쿨_브라이트, 겨울쿨_딥
- 립스틱 톤(제품): 제품 자체의 색상 특성
- 이 모듈이 하는 일: 립스틱 BGR → "이 립스틱이 어떤 퍼스널컬러 타입에게 어울리는가" 태깅

matcher.py의 TONE_TYPES와 동일한 체계 사용.
"""

import cv2
import numpy as np


# 퍼스널컬러 타입별 어울리는 립스틱 색상 범위 정의
# (Hue, Saturation, Value 기준 - OpenCV HSV: H 0~180, S 0~255, V 0~255)
TONE_PROFILES = {
    "봄웜_라이트": {
        "description": "밝고 부드러운 파스텔 코랄/피치",
        # 따뜻한 계열(코랄/피치/살몬), 높은 명도, 중간 채도
        "hue_range": [(0, 20)],   # 빨강~주황 계열
        "sat_range": (80, 160),
        "val_range": (160, 255),
    },
    "봄웜_브라이트": {
        "description": "선명하고 생기있는 코랄/오렌지레드",
        # 따뜻한 계열, 높은 명도, 높은 채도
        "hue_range": [(0, 20)],
        "sat_range": (160, 255),
        "val_range": (140, 255),
    },
    "가을웜_뮤트": {
        "description": "탁하고 부드러운 테라코타/브릭/브라운 누드",
        # 따뜻한 계열, 중간 명도, 낮은 채도
        "hue_range": [(0, 25)],
        "sat_range": (40, 130),
        "val_range": (80, 160),
    },
    "가을웜_딥": {
        "description": "어둡고 진한 버건디/와인/딥브라운",
        # 따뜻한 계열, 낮은 명도
        "hue_range": [(0, 20)],
        "sat_range": (60, 200),
        "val_range": (30, 100),
    },
    "여름쿨_라이트": {
        "description": "맑고 연한 로즈핑크/베이비핑크/라이트모브",
        # 차가운 계열(핑크/라벤더), 높은 명도, 낮은 채도
        "hue_range": [(140, 175)],
        "sat_range": (30, 120),
        "val_range": (160, 255),
    },
    "여름쿨_뮤트": {
        "description": "탁하고 부드러운 모브/로즈우드/뮤트핑크",
        # 차가운 계열, 중간 명도, 낮은 채도
        "hue_range": [(130, 175)],
        "sat_range": (40, 130),
        "val_range": (80, 160),
    },
    "겨울쿨_브라이트": {
        "description": "선명하고 강렬한 트루레드/로즈레드/비비드플럼",
        # 차가운 계열, 중간~높은 명도, 높은 채도
        "hue_range": [(140, 180), (0, 5)],
        "sat_range": (160, 255),
        "val_range": (80, 200),
    },
    "겨울쿨_딥": {
        "description": "어둡고 차가운 딥버건디/다크플럼/블랙체리",
        # 차가운 계열, 낮은 명도, 높은 채도
        "hue_range": [(130, 180), (0, 5)],
        "sat_range": (100, 255),
        "val_range": (20, 90),
    },
}


def _hue_in_ranges(h: int, ranges: list[tuple]) -> bool:
    """Hue가 지정된 범위 중 하나에 속하는지 확인"""
    return any(lo <= h <= hi for lo, hi in ranges)


def _score_against_profile(hsv: tuple, profile: dict) -> float:
    """
    HSV 값이 프로파일에 얼마나 가까운지 점수 계산 (0.0 ~ 1.0)
    각 축(H, S, V)의 범위 일치도를 평균냄
    """
    h, s, v = hsv

    # Hue 점수
    hue_match = _hue_in_ranges(h, profile["hue_range"])
    hue_score = 1.0 if hue_match else 0.0

    # Saturation 점수 (범위 중심에 가까울수록 높은 점수)
    s_lo, s_hi = profile["sat_range"]
    if s_lo <= s <= s_hi:
        s_center = (s_lo + s_hi) / 2
        s_score = 1.0 - abs(s - s_center) / ((s_hi - s_lo) / 2 + 1e-6) * 0.5
    else:
        dist = min(abs(s - s_lo), abs(s - s_hi))
        s_score = max(0.0, 1.0 - dist / 40)

    # Value 점수
    v_lo, v_hi = profile["val_range"]
    if v_lo <= v <= v_hi:
        v_center = (v_lo + v_hi) / 2
        v_score = 1.0 - abs(v - v_center) / ((v_hi - v_lo) / 2 + 1e-6) * 0.5
    else:
        dist = min(abs(v - v_lo), abs(v - v_hi))
        v_score = max(0.0, 1.0 - dist / 40)

    # Hue 가중치 높임 (웜/쿨 구분이 가장 중요)
    return hue_score * 0.5 + s_score * 0.25 + v_score * 0.25


def analyze_lipstick_color(bgr: list[int]) -> dict:
    """
    립스틱 BGR → 어울리는 퍼스널컬러 타입 분석

    Args:
        bgr: [B, G, R] 리스트

    Returns:
        {
            "recommended_for": "봄웜_브라이트",  # 가장 잘 어울리는 톤
            "secondary_tones": ["봄웜_라이트"],   # 차선 추천 톤
            "hex": "#RRGGBB",
            "hsv": {"h": ..., "s": ..., "v": ...},
            "scores": {...},                       # 전체 톤별 점수 (디버깅용)
            "description": "선명하고 생기있는 코랄/오렌지레드",
        }
    """
    # BGR → HSV 변환
    pixel = np.uint8([[bgr]])
    hsv_arr = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0][0]
    h, s, v = int(hsv_arr[0]), int(hsv_arr[1]), int(hsv_arr[2])

    # BGR → RGB → HEX
    r, g, b = bgr[2], bgr[1], bgr[0]
    hex_color = f"#{r:02x}{g:02x}{b:02x}"

    # 전체 톤 프로파일 대비 점수 계산
    scores = {}
    for tone_name, profile in TONE_PROFILES.items():
        scores[tone_name] = round(_score_against_profile((h, s, v), profile), 3)

    # 점수 내림차순 정렬
    sorted_tones = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    best_tone = sorted_tones[0][0]
    best_score = sorted_tones[0][1]

    # 2위 톤 (점수가 best의 70% 이상이면 차선으로 포함)
    secondary = [
        t for t, sc in sorted_tones[1:]
        if sc >= best_score * 0.7 and sc > 0.3
    ]

    return {
        "recommended_for": best_tone,
        "secondary_tones": secondary[:2],  # 최대 2개
        "hex": hex_color,
        "hsv": {"h": h, "s": s, "v": v},
        "scores": dict(sorted_tones),
        "description": TONE_PROFILES[best_tone]["description"],
    }


def analyze_batch(bgr_list: list[list[int]]) -> list[dict]:
    """여러 BGR 값 일괄 분석"""
    return [analyze_lipstick_color(bgr) for bgr in bgr_list]


# 테스트
if __name__ == "__main__":
    test_colors = [
        ([100, 120, 220], "코랄 (봄웜_브라이트 예상)"),
        ([130, 150, 210], "피치 (봄웜_라이트 예상)"),
        ([80,  90,  160], "테라코타 (가을웜_뮤트 예상)"),
        ([50,  60,  110], "와인 (가을웜_딥 예상)"),
        ([150, 140, 200], "로즈핑크 (여름쿨_라이트 예상)"),
        ([110, 100, 160], "모브 (여름쿨_뮤트 예상)"),
        ([80,  60,  180], "트루레드 (겨울쿨_브라이트 예상)"),
        ([40,  30,  100], "딥플럼 (겨울쿨_딥 예상)"),
    ]

    print("립스틱 색상 → 퍼스널컬러 타입 매칭 테스트")
    print("=" * 65)
    for bgr, label in test_colors:
        result = analyze_lipstick_color(bgr)
        print(f"\nBGR {bgr}  ({label})")
        print(f"  → 추천 대상: {result['recommended_for']}")
        print(f"  → 차선 톤:   {result['secondary_tones']}")
        print(f"  → Hex:       {result['hex']}")
        print(f"  → 설명:      {result['description']}")
