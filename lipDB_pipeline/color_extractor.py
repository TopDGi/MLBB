import cv2
import numpy as np


def extract_center_bgr(image_bytes: bytes, crop_ratio: float = 0.4, k: int = 3) -> list[int] | None:
    """
    이미지 중앙 영역만 샘플링해 K-Means로 대표 BGR 추출.

    전체 이미지 대신 중앙 crop_ratio 비율만 사용하는 이유:
    스와치 이미지의 가장자리는 흰색/회색 배경이나 그림자가 섞여
    색상 추출 정확도를 떨어뜨리기 때문.
    """
    arr = np.frombuffer(image_bytes, np.uint8)
    img = cv2.imdecode(arr, cv2.IMREAD_COLOR)
    if img is None:
        return None

    h, w = img.shape[:2]
    cy, cx = h // 2, w // 2
    dh = max(1, int(h * crop_ratio / 2))
    dw = max(1, int(w * crop_ratio / 2))
    cropped = img[cy - dh:cy + dh, cx - dw:cx + dw]

    # 연산 효율을 위해 50x50으로 리사이즈
    resized = cv2.resize(cropped, (50, 50), interpolation=cv2.INTER_AREA)
    pixels = resized.reshape(-1, 3).astype(np.float32)

    criteria = (cv2.TERM_CRITERIA_EPS + cv2.TERM_CRITERIA_MAX_ITER, 10, 1.0)
    _, labels, centers = cv2.kmeans(pixels, k, None, criteria, 10, cv2.KMEANS_RANDOM_CENTERS)

    # 교체 — 가장 채도 높은 클러스터 선택
    best_idx = 0
    best_sat = -1
    for idx, center in enumerate(centers):
        bgr = center.astype(np.uint8)
        pixel = np.uint8([[bgr]])
        hsv = cv2.cvtColor(pixel, cv2.COLOR_BGR2HSV)[0][0]
        sat = int(hsv[1])
        if sat > best_sat:
            best_sat = sat
            best_idx = idx

    # 채도가 너무 낮으면 (배경만 있는 이미지) None 반환
    if best_sat < 20:
        return None

    dominant = centers[best_idx].astype(int)
    return dominant.tolist()
