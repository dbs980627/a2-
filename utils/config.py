"""
API 키 및 환경설정 로드 유틸리티

- .env 파일 또는 시스템 환경 변수에서 API 키를 읽어온다.
- 코드에 API 키를 직접 작성하지 않는다 (과제 필수 요구사항).
"""

import os
from dotenv import load_dotenv


def load_api_keys():
    """
    .env 파일을 로드하고 필요한 API 키를 딕셔너리로 반환한다.

    Returns:
        dict: {"copa_api_key": str | None}
    """
    load_dotenv()
    copa_key = os.getenv("COPA_API_KEY")
    return {"copa_api_key": copa_key}


def validate_api_keys(keys: dict) -> bool:
    """
    필수 API 키가 존재하는지 확인하고, 없으면 안내 메시지를 출력한다.

    Args:
        keys: load_api_keys()가 반환한 딕셔너리

    Returns:
        bool: 모든 필수 키가 존재하면 True, 하나라도 없으면 False
    """
    if not keys.get("copa_api_key"):
        print("❌ COPA_API_KEY가 설정되지 않았습니다.")
        print("   1) 프로젝트 루트에 .env 파일을 만들고")
        print("   2) COPA_API_KEY=<발급받은 코디세이 API 키> 형식으로 키를 추가한 뒤")
        print("   3) 프로그램을 다시 실행해주세요.")
        return False
    return True
