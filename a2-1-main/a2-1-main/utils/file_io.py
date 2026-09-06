"""
파일 입출력 유틸리티: 브리프 JSON 로드, 결과 저장, 출력 폴더 관리
"""

import json
import os


REQUIRED_BRIEF_FIELDS = ["industry", "target", "keywords"]


def load_brief(path: str) -> dict:
    """
    브랜드 브리프 JSON 파일을 로드하고 필수 필드를 검증한다.

    Args:
        path: 브리프 JSON 파일 경로

    Returns:
        dict: 브리프 데이터

    Raises:
        FileNotFoundError: 파일이 없을 때
        ValueError: JSON 파싱 실패 또는 필수 필드 누락 시
    """
    if not os.path.exists(path):
        raise FileNotFoundError(f"브리프 파일을 찾을 수 없습니다: {path}")

    with open(path, "r", encoding="utf-8") as f:
        try:
            brief = json.load(f)
        except json.JSONDecodeError as e:
            raise ValueError(f"브리프 파일이 올바른 JSON 형식이 아닙니다: {e}")

    missing = [field for field in REQUIRED_BRIEF_FIELDS if not brief.get(field)]
    if missing:
        raise ValueError(f"브리프 파일에 필수 필드가 누락되었습니다: {', '.join(missing)}")

    # 선택 필드 기본값 채우기
    brief.setdefault("tone", "")
    brief.setdefault("competitors", [])
    brief.setdefault("notes", "")

    return brief


def ensure_output_dir(path: str) -> str:
    """
    출력 폴더가 없으면 생성한다.

    Args:
        path: 출력 폴더 경로 (빈 문자열이면 기본값 ./output 사용)

    Returns:
        str: 실제 사용할 출력 폴더 경로
    """
    path = path.strip() or "./output"
    os.makedirs(path, exist_ok=True)
    return path


def save_json(data: dict, path: str) -> None:
    """결과 딕셔너리를 JSON 파일로 저장한다."""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
