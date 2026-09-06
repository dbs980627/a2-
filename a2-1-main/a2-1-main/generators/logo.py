"""
로고 시안 생성 모듈

- Codyssey 이미지 생성 API(/api/v1/images)를 호출하여 로고 시안을 PNG로 저장한다.
- response_format을 b64_json으로 지정해 base64로 직접 수신 후 디코딩한다.

이 모듈은 JSON 텍스트 응답이 아니라 이미지 생성 API를 직접 호출하므로,
utils.llm.call_json_prompt()나 utils.prompts의 텍스트 가드레일을 사용하지 않는다.
"""

import base64
import os

import requests

BASE_URL = "https://copa.codyssey.kr"
DEFAULT_IMAGE_MODEL = "gpt-image-2"


def build_logo_prompt(brief: dict, naming: list, palette: dict) -> str:
    """
    네이밍/컬러 결과를 반영한 로고 생성 프롬프트를 만든다.

    Args:
        brief: 브랜드 브리프 딕셔너리
        naming: generate_naming()이 반환한 네이밍 후보 리스트
        palette: generate_color_palette()가 반환한 컬러 팔레트

    Returns:
        str: 이미지 생성 API에 전달할 프롬프트
    """
    brand_name = naming[0]["name_en"] if naming else brief["industry"]
    main_color = palette.get("main", {}).get("name", "")

    return (
        f"A minimal, modern vector-style logo design for a brand called '{brand_name}', "
        f"in the {brief['industry']} industry, targeting {brief['target']}. "
        f"Use {main_color} as the dominant color. Clean, flat, professional, "
        f"centered on a plain white background, no text overlay artifacts, no watermark."
    )


def generate_logos(api_key: str, prompt: str, output_dir: str, count: int = 2,
                   model: str = DEFAULT_IMAGE_MODEL) -> list:
    """
    로고 시안을 생성하고 PNG 파일로 저장한다. 개별 호출 실패는 건너뛰고 계속 진행한다.

    Args:
        api_key: Codyssey API 키
        prompt: 로고 생성 프롬프트
        output_dir: 저장할 폴더 경로
        count: 생성할 로고 개수 (2~3 권장)
        model: 사용할 이미지 생성 모델명

    Returns:
        list[str]: 저장된 PNG 파일 경로 목록 (실패한 항목은 제외)
    """
    saved_paths = []
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "prompt": prompt,
        "size": "1024x1024",
        "response_format": "b64_json",
    }

    for i in range(1, count + 1):
        try:
            response = requests.post(
                f"{BASE_URL}/api/v1/images",
                headers=headers,
                json=payload,
                timeout=120,
            )
            response.raise_for_status()

            b64_data = response.json()["result"]["images"][0]["b64_json"]
            file_path = os.path.join(output_dir, f"logo_{i:02d}.png")

            with open(file_path, "wb") as f:
                f.write(base64.b64decode(b64_data))

            saved_paths.append(file_path)
            print(f"  - 저장: {file_path}")

        except Exception as e:
            print(f"  ⚠️ 로고 시안 {i} 생성 실패: {e}")

    return saved_paths
