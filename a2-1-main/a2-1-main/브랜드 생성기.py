"""
AI 브랜드 아이덴티티 생성기 - 메인 실행 파일

브랜드 브리프(JSON)를 입력받아 다음을 순서대로 생성한다.
  [1/5] 브랜드 네이밍
  [2/5] 슬로건
  [3/5] 브랜드 스토리
  [4/5] 컬러 팔레트 (+ PNG 시각화)
  [5/5] 로고 시안 (PNG)

모든 텍스트 결과는 brand_result.json으로, 이미지는 개별 PNG로 저장한다.
각 단계는 독립적으로 에러 처리되며, 한 단계가 실패해도 다음 단계를 계속 진행한다.
실패 이력은 result["errors"]에 {stage, message} 형태로 기록되어, 최종 JSON을
사후 분석할 수 있도록 한다.
"""

from datetime import datetime

from utils.config import load_api_keys, validate_api_keys
from utils.file_io import load_brief, ensure_output_dir, save_json
from generators.naming import generate_naming
from generators.slogan import generate_slogan
from generators.story import generate_story
from generators.color import generate_color_palette, visualize_palette
from generators.logo import build_logo_prompt, generate_logos


def _record_failure(result: dict, stage: str, error: Exception, message_prefix: str) -> None:
    """실패를 콘솔에 출력하고 result["errors"]에도 함께 기록한다."""
    print(f"  ⚠️ {message_prefix}: {error}")
    result["errors"].append({"stage": stage, "message": str(error)})


def main():
    print("\n🎨 AI 브랜드 아이덴티티 생성기\n")

    # --- API 키 로드 및 검증 ---
    keys = load_api_keys()
    if not validate_api_keys(keys):
        return
    api_key = keys["copa_api_key"]

    # --- 사용자 입력 ---
    brief_path = input(
        "브리프 파일 경로를 입력하세요 (예: brief.json, 엔터 시 ./brief.json): "
    ).strip() or "./brief.json"
    output_dir_input = input("출력 폴더 경로를 입력하세요 (엔터 시 ./output): ").strip()
    output_dir = ensure_output_dir(output_dir_input)

    # --- 브리프 로드 ---
    try:
        brief = load_brief(brief_path)
    except (FileNotFoundError, ValueError) as e:
        print(f"❌ 브리프 로드 실패: {e}")
        return

    result = {
        "brief": brief,
        "naming": [],
        "slogans": [],
        "story": "",
        "color_palette": {},
        "logos": [],
        "errors": [],
        "generated_at": datetime.now().isoformat(timespec="seconds"),
    }

    # --- [1/5] 브랜드 네이밍 ---
    print("[1/5] 브랜드 네이밍 생성 중...")
    try:
        result["naming"] = generate_naming(api_key, brief)
        for item in result["naming"]:
            print(f"  - {item.get('name')} ({item.get('name_en')}): {item.get('meaning')}")
    except (RuntimeError, ValueError) as e:
        _record_failure(result, "naming", e, "네이밍 생성 실패")

    # --- [2/5] 슬로건 ---
    print("[2/5] 슬로건 생성 중...")
    try:
        result["slogans"] = generate_slogan(api_key, brief)
        for slogan in result["slogans"]:
            print(f'  - "{slogan}"')
    except (RuntimeError, ValueError) as e:
        _record_failure(result, "slogan", e, "슬로건 생성 실패")

    # --- [3/5] 브랜드 스토리 ---
    print("[3/5] 브랜드 스토리 생성 중...")
    try:
        result["story"] = generate_story(api_key, brief)
        print(f"  - 스토리 생성 완료 ({len(result['story'])}자)")
    except (RuntimeError, ValueError) as e:
        _record_failure(result, "story", e, "스토리 생성 실패")

    # --- [4/5] 컬러 팔레트 ---
    print("[4/5] 컬러 팔레트 생성 중...")
    try:
        result["color_palette"] = generate_color_palette(api_key, brief, story=result["story"])
        main_color = result["color_palette"].get("main", {}).get("hex", "")
        sub_colors = [c.get("hex", "") for c in result["color_palette"].get("sub", [])]
        print(f"  - 메인: {main_color}")
        print(f"  - 서브: {', '.join(sub_colors)}")

        palette_path = visualize_palette(result["color_palette"], output_dir)
        print(f"  - 저장: {palette_path}")
    except (RuntimeError, ValueError) as e:
        _record_failure(result, "color", e, "컬러 팔레트 생성 실패")

    # --- [5/5] 로고 시안 ---
    print("[5/5] 로고 시안 생성 중...")
    try:
        logo_prompt = build_logo_prompt(brief, result["naming"], result["color_palette"])
        result["logos"] = generate_logos(api_key, logo_prompt, output_dir, count=2)
    except Exception as e:
        _record_failure(result, "logo", e, "로고 시안 생성 실패")

    # --- 결과 저장 ---
    result_json_path = f"{output_dir}/brand_result.json"
    save_json(result, result_json_path)

    if result["errors"]:
        print(f"\n⚠️ {len(result['errors'])}개 단계에서 오류가 발생했습니다 (brand_result.json의 errors 필드 참고).")
    print(f"\n✅ 완료! {output_dir}/ 폴더를 확인하세요.")


if __name__ == "__main__":
    main()
