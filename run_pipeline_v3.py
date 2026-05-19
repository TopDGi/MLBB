import cv2
import os
import glob
from harmony_analyzer import HarmonyAnalyzer
from matcher_v3 import LipstickMatcher_v2
from visualizer_v2 import LipVisualizer_v2
from result_matrix import build_matrix


def print_top4(base_name: str, top4_result: dict) -> None:
    """top-4 추천 결과 터미널 출력"""
    tone  = top4_result.get("user_diagnosed_tone", "")
    hint  = top4_result.get("tone_lip_hint", "")
    style = top4_result.get("suggested_style", "")
    top4  = top4_result.get("top4", [])

    print(f"""
  ┌─ 💄 {base_name} ───────────────────────────────────
  │  [퍼스널 톤]   {tone}
  │  [어울리는 립] {hint}
  │  [추천 스타일] {style}
  │""")

    for item in top4:
        rank  = item["rank"]
        name  = item["name"]
        brand = item.get("brand", "")
        score = item["score"]
        hex_  = item.get("hex", "")
        link  = item.get("link", "")
        medal = ["🥇", "🥈", "🥉", "  "][rank - 1]
        print(f"  │  {medal} {rank}위  {brand} {name}")
        print(f"  │       점수: {score}pt  색상: {hex_}")
        if link:
            print(f"  │       링크: {link}")
        print("  │")

    print(f"  └────────────────────────────────────────────────────")


def run_automated_pipeline(input_folder: str = 'test_images') -> None:
    # 1. 초기화 (반복문 밖에서 한 번만)
    analyzer   = HarmonyAnalyzer()
    matcher    = LipstickMatcher_v2()
    visualizer = LipVisualizer_v2()

    # 2. 이미지 파일 수집 (_result / _top4 파일 제외)
    types = ('*.jpg', '*.jpeg', '*.png')
    image_files = []
    for t in types:
        image_files.extend(glob.glob(os.path.join(input_folder, t)))
    image_files = [
        f for f in image_files
        if "_result" not in os.path.basename(f)
        and "_top4" not in os.path.basename(f)
    ]

    if not image_files:
        print(f"⚠️ '{input_folder}' 폴더에 이미지 파일이 없습니다.")
        return

    print(f"\n🚀 총 {len(image_files)}개의 이미지 분석을 시작합니다.")
    print("=" * 55)

    success, fail = 0, 0

    for img_path in image_files:
        base_name = os.path.basename(img_path)
        file_name, ext = os.path.splitext(base_name)
        matrix_path = os.path.join(input_folder, f"{file_name}_top4{ext}")

        print(f"\n--- 💄 {base_name} 분석 중... ---")

        try:
            # 3. 얼굴 분석
            analysis_result = analyzer.analyze(img_path)
            if "error" in analysis_result:
                print(f"  ❌ 인식 실패: {analysis_result['error']}")
                fail += 1
                continue

            # 4. top-4 추천
            top4_result = matcher.get_top4(analysis_result)

            # 5. 터미널 출력
            print_top4(base_name, top4_result)

            # 6. 2×2 매트릭스 이미지 저장
            build_matrix(
                image_path=img_path,
                analysis_result=analysis_result,
                top4_result=top4_result,
                visualizer=visualizer,
                output_path=matrix_path,
            )

            success += 1

        except Exception as e:
            print(f"  🔥 예외 발생: {e}")
            fail += 1

    print(f"\n{'='*55}")
    print(f"✨ 완료  성공 {success}개 / 실패 {fail}개 / 전체 {len(image_files)}개")
    print(f"{'='*55}\n")


if __name__ == "__main__":
    run_automated_pipeline('test_images')