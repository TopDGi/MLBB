import cv2
import numpy as np


class LipVisualizer_v2:
    def __init__(self):
        self.LIPS_OUTLINE_INDICES = [
        # outer upper lip (left → right)
        61, 185, 40, 39, 37, 0, 267, 269, 270, 409, 291,
        # outer lower lip (right → left, back to start)
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

        # 입술 밖으로 색이 삐져나가는 것을 방지
        kernel = np.ones((3, 3), np.uint8)
        mask = cv2.erode(mask, kernel, iterations=2)

        blur_size = int(w * 0.015) | 1  # 반드시 홀수
        mask = cv2.GaussianBlur(mask, (blur_size, blur_size), 0)

        return mask

    def apply_lipstick(self, image_source, landmarks, color_bgr, intensity=0.6):
        """image_source: 파일 경로(str) 또는 BGR numpy array 둘 다 허용"""
        if isinstance(image_source, np.ndarray):
            img = image_source.copy()
        else:
            img = cv2.imdecode(
                np.fromfile(image_source, dtype=np.uint8),
                cv2.IMREAD_COLOR,
            )
        if img is None:
            return None

        base = img.astype(np.float32) / 255.0
        h, w, _ = img.shape

        mask = self._create_refined_mask(img, landmarks)
        alpha = mask.astype(np.float32) / 255.0 * intensity
        alpha = cv2.merge([alpha, alpha, alpha])

        color_layer = np.full_like(base, np.array(color_bgr, dtype=np.float32) / 255.0)

        # Soft Light 블렌딩: 원본 밝기(Luminosity)를 유지하며 색을 입힘
        blend = np.where(
            color_layer <= 0.5,
            base * (color_layer + 0.5),
            1 - (1 - base) * (1 - (color_layer - 0.5))
        )

        result = base * (1 - alpha) + blend * alpha
        return np.clip(result * 255, 0, 255).astype(np.uint8)