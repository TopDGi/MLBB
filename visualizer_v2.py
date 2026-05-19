from unittest import result

import cv2
import numpy as np


# ── 질감 모드 상수 ─────────────────────────────────
TEXTURE_MATTE    = "matte"       # 균일한 색, 반사 없음 (기존)
TEXTURE_GLOSSY   = "glossy"      # 중앙 하이라이트 + 광택
TEXTURE_TINT     = "tint"        # 반투명, 피부 텍스처 살아있음
TEXTURE_GRADIENT = "gradient"    # 중앙 진하고 외곽 옅음


class LipVisualizer_v2:
    def __init__(self):
        self.LIPS_OUTLINE_INDICES = [
            # outer upper lip (left to right)
            61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291,
            # outer lower lip (right to left, back to start)
            375, 321, 405, 314, 17, 84, 181, 91, 146, 61
        ]

    def _create_refined_mask(self, image, landmarks):
        h, w, _ = image.shape
        lips_points = np.array([
            [int(landmarks[idx].x * w), int(landmarks[idx].y * h)]
            for idx in self.LIPS_OUTLINE_INDICES
        ], dtype=np.int32)

        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [lips_points], 255)

        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=2)

        blur_size = int(w * 0.015) | 1
        mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)
        return mask

    def _get_lip_bbox(self, mask):
        """마스크에서 입술 bounding box 반환"""
        ys, xs = np.where(mask > 30)
        if len(xs) == 0:
            return None
        return int(xs.min()), int(ys.min()), int(xs.max()), int(ys.max())

    def _make_gloss_highlight(self, mask, bbox):
        """글로시 하이라이트 레이어: 상단 중앙에 타원형 흰 빛"""
        h, w = mask.shape
        highlight = np.zeros((h, w), dtype=np.float32)
        if bbox is None:
            return highlight

        x0, y0, x1, y1 = bbox
        lip_w = x1 - x0
        lip_h = y1 - y0
        cx = (x0 + x1) // 2
        cy = y0 + int(lip_h * 0.30)

        ell_w = max(int(lip_w * 0.35), 4)
        ell_h = max(int(lip_h * 0.22), 2)

        temp = np.zeros((h, w), dtype=np.uint8)
        cv2.ellipse(temp, (cx, cy), (ell_w, ell_h), 0, 0, 360, 255, -1)
        temp_f = temp.astype(np.float32) / 255.0

        blur = max(int(lip_w * 0.08) | 1, 3)
        highlight = cv2.GaussianBlur(temp_f, (blur * 4 + 1, blur * 4 + 1), blur)
        highlight *= (mask.astype(np.float32) / 255.0)
        return highlight

    def _make_gradient_alpha(self, mask):
        """거리 변환 기반 그라데이션 알파: 중앙 진하고 외곽 옅음"""
        dist = cv2.distanceTransform(mask, cv2.DIST_L2, 5)
        if dist.max() > 0:
            dist = dist / dist.max()
        return dist

    # ── 질감별 블렌딩 ─────────────────────────────

    def _blend_matte(self, base, color_layer, alpha_3ch):
        """매트: Soft Light 블렌딩 (기존)"""
        blend = np.where(
            color_layer <= 0.5,
            base * (color_layer + 0.5),
            1 - (1 - base) * (1 - (color_layer - 0.5))
        )
        return base * (1 - alpha_3ch) + blend * alpha_3ch

    def _blend_glossy(self, base, color_layer, mask, bbox, intensity):
        """
        글로시:
        1. Soft Light 기본 색상
        2. 상단 중앙 타원형 흰 하이라이트 (Screen 블렌딩)
        3. 마스크 내 채도 살짝 올림
        """
        alpha_base = mask.astype(np.float32) / 255.0 * intensity
        alpha_3ch  = cv2.merge([alpha_base, alpha_base, alpha_base])

        blend = np.where(
            color_layer <= 0.5,
            base * (color_layer + 0.5),
            1 - (1 - base) * (1 - (color_layer - 0.5))
        )
        result = base * (1 - alpha_3ch) + blend * alpha_3ch

        # 하이라이트 (Screen)
        highlight = self._make_gloss_highlight(mask, bbox)
        hl_3ch = cv2.merge([highlight, highlight, highlight]) * 0.55
        result  = 1 - (1 - result) * (1 - hl_3ch)

        # 채도 보정
        mask_f = mask.astype(np.float32) / 255.0
        hsv = cv2.cvtColor(
            np.clip(result * 255, 0, 255).astype(np.uint8), cv2.COLOR_BGR2HSV
        ).astype(np.float32)
        hsv[:, :, 1] = np.clip(hsv[:, :, 1] + mask_f * 18, 0, 255)
        result = cv2.cvtColor(hsv.astype(np.uint8), cv2.COLOR_HSV2BGR).astype(np.float32) / 255.0

        return np.clip(result, 0, 1)

    def _blend_tint(self, base, color_layer, alpha_3ch):
        """
        틴트: 반투명, 피부 텍스처 살아있음
        Multiply + Soft Light 혼합, intensity 낮게
        """
        multiply = np.clip(base * color_layer * 2.0, 0, 1)
        soft = np.where(
            color_layer <= 0.5,
            base * (color_layer + 0.5),
            1 - (1 - base) * (1 - (color_layer - 0.5))
        )
        blend = soft * 0.6 + multiply * 0.4
        tint_alpha = alpha_3ch * 0.65
        return base * (1 - tint_alpha) + blend * tint_alpha

    def _blend_gradient(self, base, color_layer, mask, intensity):
        """
        그라데이션: 중앙 진하고 외곽 옅음
        거리 변환 기반 알파
        """
        dist_alpha = self._make_gradient_alpha(mask)
        grad_alpha = np.power(dist_alpha, 0.7) * intensity
        alpha_3ch  = cv2.merge([grad_alpha, grad_alpha, grad_alpha])

        blend = np.where(
            color_layer <= 0.5,
            base * (color_layer + 0.5),
            1 - (1 - base) * (1 - (color_layer - 0.5))
        )
        return base * (1 - alpha_3ch) + blend * alpha_3ch

    # ── Public API ────────────────────────────────

    def apply_lipstick(
        self,
        image_source,
        landmarks,
        color_bgr,
        intensity: float = 0.6,
        texture: str = TEXTURE_MATTE,
    ):
        """
        립스틱 적용

        Args:
            image_source : 파일 경로(str) 또는 BGR numpy array
            landmarks    : MediaPipe 랜드마크
            color_bgr    : [B, G, R] 립 색상
            intensity    : 0.0~1.0 (색상 강도)
            texture      : "matte" | "glossy" | "tint" | "gradient"

        Returns:
            BGR numpy array (uint8)
        """
        if isinstance(image_source, np.ndarray):
            img = image_source.copy()
        else:
            img = cv2.imdecode(
                np.fromfile(image_source, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
        if img is None:
            return None

        base  = img.astype(np.float32) / 255.0
        mask  = self._create_refined_mask(img, landmarks)
        bbox  = self._get_lip_bbox(mask)
        alpha = mask.astype(np.float32) / 255.0 * intensity
        alpha_3ch   = cv2.merge([alpha, alpha, alpha])
        color_layer = np.full_like(base, np.array(color_bgr, dtype=np.float32) / 255.0)

        if texture == TEXTURE_GLOSSY:
            result = self._blend_glossy(base, color_layer, mask, bbox, intensity)
        elif texture == TEXTURE_TINT:
            result = self._blend_tint(base, color_layer, alpha_3ch)
        elif texture == TEXTURE_GRADIENT:
            result = self._blend_gradient(base, color_layer, mask, intensity)
        else:
            result = self._blend_matte(base, color_layer, alpha_3ch)

        # 교체
        result_uint8 = np.clip(result * 255, 0, 255).astype(np.uint8)

        # 립 마스크 영역 평균 BGR 추출
        mask_bool = mask > 30
        if mask_bool.any():
            lip_pixels = result_uint8[mask_bool]
            blended_bgr = lip_pixels.mean(axis=0).astype(int).tolist()
        else:
            blended_bgr = color_bgr

        return result_uint8, blended_bgr