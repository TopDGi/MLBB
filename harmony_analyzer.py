import numpy as np
import mediapipe as mp
from mediapipe.tasks import python
from mediapipe.tasks.python import vision


def _white_balance(image: np.ndarray) -> np.ndarray:
    """
    Gray World 화이트밸런스 보정
    ─────────────────────────────
    가정: 이미지 전체의 평균 색상은 회색(무채색)이어야 한다.
    조명 색온도 차이(스튜디오 블루, 형광등 옐로우 등)를
    채널별 스케일링으로 제거해서 피부색을 정규화함.

    스튜디오 사진 (블루-화이트 조명) → 보정 후 중립
    일상 사진 (웜 조명/자동 화밸)   → 보정 후 중립
    """
    image = image.astype(np.float32)
    b_mean, g_mean, r_mean = (
        np.mean(image[:, :, 0]),
        np.mean(image[:, :, 1]),
        np.mean(image[:, :, 2]),
    )
    gray_mean = (b_mean + g_mean + r_mean) / 3.0

    # 각 채널을 전체 평균에 맞게 스케일
    image[:, :, 0] = np.clip(image[:, :, 0] * (gray_mean / (b_mean + 1e-6)), 0, 255)
    image[:, :, 1] = np.clip(image[:, :, 1] * (gray_mean / (g_mean + 1e-6)), 0, 255)
    image[:, :, 2] = np.clip(image[:, :, 2] * (gray_mean / (r_mean + 1e-6)), 0, 255)

    return image.astype(np.uint8)


def _imread_korean(image_path: str) -> np.ndarray:
    """
    한글/유니코드 경로 대응 이미지 로드
    cv2.imread()는 Windows에서 한글 경로를 못 읽는 경우가 있음.
    np.fromfile + imdecode로 우회.
    """
    import cv2
    return cv2.imdecode(
        np.fromfile(image_path, dtype=np.uint8),
        cv2.IMREAD_COLOR,
    )


class HarmonyAnalyzer:
    def __init__(self):
        model_path = 'face_landmarker.task'
        base_options = python.BaseOptions(model_asset_path=model_path)
        options = vision.FaceLandmarkerOptions(
            base_options=base_options,
            output_face_blendshapes=True,
            output_facial_transformation_matrixes=True,
            num_faces=1,
            running_mode=vision.RunningMode.IMAGE,
        )
        self.detector = vision.FaceLandmarker.create_from_options(options)

    def analyze(self, image_path: str) -> dict:
        import cv2

        # 1. 이미지 로드 (한글 경로 대응)
        image = _imread_korean(image_path)
        if image is None:
            return {"error": f"이미지를 로드할 수 없습니다: {image_path}"}

        # 2. 화이트밸런스 보정 (조명 영향 제거)
        image = _white_balance(image)

        # 3. MediaPipe 분석
        image_rgb = cv2.cvtColor(image, cv2.COLOR_BGR2RGB)
        mp_image  = mp.Image(image_format=mp.ImageFormat.SRGB, data=image_rgb)
        detection_result = self.detector.detect(mp_image)

        if not detection_result.face_landmarks:
            return {"error": "얼굴을 인식하지 못했습니다. 정면 사진인지 확인해주세요."}

        # 4. 데이터 추출
        landmarks = detection_result.face_landmarks[0]
        h, w, _   = image.shape

        skin_color = self._extract_area_color(image, landmarks, "skin")
        lips_color = self._extract_area_color(image, landmarks, "lips")

        face_width = np.linalg.norm(
            np.array([landmarks[234].x, landmarks[234].y]) -
            np.array([landmarks[454].x, landmarks[454].y])
        )
        face_height = np.linalg.norm(
            np.array([landmarks[10].x, landmarks[10].y]) -
            np.array([landmarks[152].x, landmarks[152].y])
        )
        face_ratio = face_width / face_height

        return {
            "raw_landmarks":  landmarks,
            "skin_color_bgr": skin_color,
            "lips_color_bgr": lips_color,
            "face_ratio":     face_ratio,
        }

    def _extract_area_color(self, image: np.ndarray, landmarks, area_type: str) -> list[int]:
        """특정 영역(피부/입술)의 대표 BGR 색상 추출"""
        import cv2
        h, w, _ = image.shape

        if area_type == "lips":
            # 입술 외곽 23포인트 (visualizer_v2와 동일하게 통일)
            indices = [
                61, 146, 91, 181, 84, 17, 314, 405,
                321, 375, 291, 409, 270, 269, 267, 0,
                37, 39, 40, 185, 61,
            ]
        else:
            # 볼 중앙 (눈가/그림자 영향 최소화)
            # 왼쪽 볼: 205, 206, 207, 187
            # 오른쪽 볼: 425, 426, 427, 411
            indices = [205, 206, 207, 187, 425, 426, 427, 411]

        points = np.array([
            [int(landmarks[idx].x * w), int(landmarks[idx].y * h)]
            for idx in indices
        ])
        mask = np.zeros((h, w), dtype=np.uint8)
        cv2.fillPoly(mask, [points], 255)

        mean_val = cv2.mean(image, mask=mask)[:3]
        return [int(c) for c in mean_val]