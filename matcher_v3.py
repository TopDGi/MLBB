import json
from unittest import result
import numpy as np
import cv2
import os

# ──────────────────────────────────────────────
# 8타입 퍼스널컬러 체계
# ──────────────────────────────────────────────
# 웜 계열 (봄/가을)
#   봄웜_라이트    : 밝고 부드러운 파스텔, 높은 명도 + 중채도
#   봄웜_브라이트  : 선명하고 생기있는, 높은 명도 + 높은 채도
#   가을웜_뮤트    : 탁하고 부드러운 어스톤, 중명도 + 낮은 채도
#   가을웜_딥      : 어둡고 진한 딥톤, 낮은 명도 + 중채도
#
# 쿨 계열 (여름/겨울)
#   여름쿨_라이트  : 맑고 연한 파스텔, 높은 명도 + 낮은 채도
#   여름쿨_뮤트    : 탁하고 부드러운, 중명도 + 낮은 채도
#   겨울쿨_브라이트: 선명하고 강렬한, 중명도 + 높은 채도
#   겨울쿨_딥      : 어둡고 차가운, 낮은 명도 + 높은 채도
# ──────────────────────────────────────────────

TONE_TYPES = [
    "봄웜_라이트",
    "봄웜_브라이트",
    "가을웜_뮤트",
    "가을웜_딥",
    "여름쿨_라이트",
    "여름쿨_뮤트",
    "겨울쿨_브라이트",
    "겨울쿨_딥",
]

TONE_LIP_HINT = {
    "봄웜_라이트":     "코랄, 피치, 살몬, 밝은 핑크",
    "봄웜_브라이트":   "비비드 코랄, 오렌지레드, 선명한 핑크",
    "가을웜_뮤트":     "테라코타, 브릭레드, 브라운 누드",
    "가을웜_딥":       "버건디, 와인, 딥 브라운",
    "여름쿨_라이트":   "로즈핑크, 베이비핑크, 라이트 모브",
    "여름쿨_뮤트":     "모브, 로즈우드, 뮤트 핑크",
    "겨울쿨_브라이트": "트루레드, 로즈레드, 비비드 플럼",
    "겨울쿨_딥":       "딥 버건디, 다크 플럼, 블랙체리",
}


class LipstickMatcher_v2:
    def __init__(self, db_path='lipstick_db.json'):
        self.db_path = db_path
        self.lipstick_db = self._load_db()

    def _load_db(self):
        if os.path.exists(self.db_path):
            with open(self.db_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        else:
            print(f"⚠️ {self.db_path}를 찾을 수 없어 기본 데이터를 사용합니다.")
            return [
                {"name": "기본 제품", "tone": "봄웜_브라이트", "bgr": [100, 100, 200], "link": ""}
            ]

    def _bgr_to_hsv(self, bgr_list):
        pixel = np.uint8([[bgr_list]])
        return cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0][0]

    def _diagnose_personal_tone(self, skin_bgr):
        """피부색 BGR → 8타입 퍼스널컬러 진단 (모두 피부색 기반)"""
        h, s, v = self._bgr_to_hsv(skin_bgr)

        is_warm         = (5 <= h <= 22)
        is_light        = v >= 150
        is_deep         = v < 130
        is_bright_chroma = s >= 40

        if is_warm:
            if is_light:
                return "봄웜_브라이트" if is_bright_chroma else "봄웜_라이트"
            elif is_deep:
                return "가을웜_딥"
            else:
                return "가을웜_뮤트"
        else:
            if is_light:
                return "여름쿨_라이트"
            elif is_deep:
                return "겨울쿨_딥" if is_bright_chroma else "여름쿨_뮤트"
            else:
                return "겨울쿨_브라이트" if is_bright_chroma else "여름쿨_뮤트"

    def _get_candidates(self, user_tone: str) -> list:
        ADJACENT = {
            "봄웜_라이트":      ["봄웜_브라이트", "가을웜_뮤트"],
            "봄웜_브라이트":    ["봄웜_라이트", "가을웜_뮤트"],
            "가을웜_뮤트":      ["봄웜_라이트", "가을웜_딥"],
            "가을웜_딥":        ["가을웜_뮤트", "봄웜_브라이트"],
            "여름쿨_라이트":    ["여름쿨_뮤트", "겨울쿨_딥"],
            "여름쿨_뮤트":      ["여름쿨_라이트", "겨울쿨_딥"],
            "겨울쿨_브라이트":  ["겨울쿨_딥", "여름쿨_뮤트"],
            "겨울쿨_딥":        ["겨울쿨_브라이트", "여름쿨_뮤트"],
        }

        def pick(tone, n):
            """특정 톤에서 최대 n개 랜덤 샘플"""
            pool = [i for i in self.lipstick_db if i.get("tone") == tone]
            #import random                                   # <- 랜덤 샘플링 부분
            #return random.sample(pool, min(n, len(pool)))   # <- 랜덤 샘플링 부분
            return pool[:n]
        
        exact = pick(user_tone, 4)
        needed = 8 - len(exact)

        result = list(exact)
        seen = {i["name"] for i in result}

        for adj_tone in ADJACENT.get(user_tone, []):
            if needed <= 0:
                break
            per_tone = max(1, needed // 2)
            for item in pick(adj_tone, per_tone):
                if item["name"] not in seen:
                    result.append(item)
                    seen.add(item["name"])
                    needed -= 1

        return result

    def _score_all(self, candidates: list, user_lips_bgr: list) -> list[dict]:
        """
        후보군 전체를 유클리드 거리로 점수화 후 내림차순 정렬.
        반환: [{"item": ..., "score": float}, ...]
        """
        user_np = np.array(user_lips_bgr)
        scored = []
        for item in candidates:
            dist  = np.linalg.norm(user_np - np.array(item["bgr"]))
            score = max(0.0, 100 * (1 - dist / 441))
            scored.append({"item": item, "score": round(score, 1)})

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored

    # ──────────────────────────────────────────────
    # Public API
    # ──────────────────────────────────────────────

    def get_top4(self, analysis_result: dict) -> dict:
        """
        top-4 추천 반환 (2×2 매트릭스 출력용)

        Returns:
            {
                "user_diagnosed_tone": str,
                "tone_lip_hint": str,
                "suggested_style": str,
                "top4": [
                    {
                        "rank": 1,
                        "name": str,
                        "brand": str,
                        "tone": str,
                        "bgr": [B, G, R],
                        "hex": str,
                        "score": float,
                        "link": str,
                        "img_url": str,
                    },
                    ...  # 최대 4개
                ]
            }
        """
        if "error" in analysis_result:
            return analysis_result

        user_skin_bgr = analysis_result["skin_color_bgr"]
        user_lips_bgr = analysis_result["lips_color_bgr"]

        user_tone  = self._diagnose_personal_tone(user_skin_bgr)
        candidates = self._get_candidates(user_tone)
        scored     = self._score_all(candidates, user_lips_bgr)

        top4 = []
        for rank, entry in enumerate(scored[:4], start=1):
            item = entry["item"]
            top4.append({
                "rank":    rank,
                "name":    item.get("name", ""),
                "brand":   item.get("brand", ""),
                "tone":    item.get("tone", ""),
                "bgr":     item.get("bgr", []),
                "hex":     item.get("hex", ""),
                "score":   entry["score"],
                "link":    item.get("link", ""),
                "img_url": item.get("img_url", ""),
            })

        suggested_style = "Gradation" if analysis_result["face_ratio"] > 0.75 else "Full-lip"

        return {
            "user_diagnosed_tone": user_tone,
            "tone_lip_hint":       TONE_LIP_HINT.get(user_tone, ""),
            "suggested_style":     suggested_style,
            "top4":                top4,
        }

    def get_recommendation_v2(self, analysis_result: dict) -> dict:
        """하위 호환용 — 1위 단일 결과 반환 (기존 run_pipeline 유지용)"""
        result = self.get_top4(analysis_result)
        if "error" in result or not result.get("top4"):
            return result

        best = result["top4"][0]
        return {
            "user_diagnosed_tone": result["user_diagnosed_tone"],
            "tone_lip_hint":       result["tone_lip_hint"],
            "recommended_product": best["name"],
            "recommended_tone":    best["tone"],
            "recommended_bgr":     best["bgr"],
            "purchase_link":       best["link"],
            "suggested_style":     result["suggested_style"],
            "match_score":         best["score"],
            "logic_version":       "3.1 (top4 + backward compat)",
        }