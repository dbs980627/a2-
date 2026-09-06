"""
생성 결과 검증 + 제한적 재생성 루프

각 generators/*.py의 출력이 프롬프트에서 요구한 형식/개수/길이 조건을
실제로 만족하는지 확인하고, 만족하지 못하면 제한된 횟수만큼 재생성을 시도한다.

복잡한 별도 평가 모델을 두는 대신 "형식 검증 + 조건 불일치 시 제한적 재생성"
구조를 선택했다 — 구현 복잡도와 실용성 사이의 균형을 위한 선택이다.
"""

import re

_HEX_RE = re.compile(r"^#[0-9A-Fa-f]{6}$")


def validate_naming(data) -> bool:
    if not isinstance(data, list) or len(data) != 4:
        return False
    return all({"name", "name_en", "meaning"} <= set(item.keys()) for item in data)


def validate_slogans(data) -> bool:
    if not isinstance(data, list) or len(data) != 3:
        return False
    return all(isinstance(s, str) and 5 <= len(s) <= 40 for s in data)


def validate_story(text) -> bool:
    if not isinstance(text, str):
        return False
    # 프롬프트가 "300자 내외"를 요구하므로 여유를 두고 150~500자를 허용 범위로 본다.
    return 150 <= len(text) <= 500


def validate_palette(data) -> bool:
    if not isinstance(data, dict) or "main" not in data or "sub" not in data:
        return False
    main = data["main"]
    subs = data.get("sub", [])
    if not isinstance(main, dict) or not _HEX_RE.match(main.get("hex", "")):
        return False
    if not (2 <= len(subs) <= 3):
        return False
    return all(isinstance(c, dict) and _HEX_RE.match(c.get("hex", "")) for c in subs)


VALIDATORS = {
    "naming": validate_naming,
    "slogan": validate_slogans,
    "story": validate_story,
    "color": validate_palette,
}


def generate_with_validation(stage: str, generate_fn, max_attempts: int = 2):
    """
    generate_fn()을 호출해 결과를 검증하고, 검증 실패 시 max_attempts 안에서
    재생성을 시도한다.

    generate_fn() 내부에서 발생하는 RuntimeError/ValueError(LLM 호출 실패,
    JSON 파싱 실패)는 여기서 잡지 않고 그대로 상위로 전달한다 — 이 함수는
    "형식은 왔지만 조건을 어긴" 응답만 다루고, API/파싱 실패는 기존
    main.py의 예외 처리 경로를 그대로 타도록 두기 위함이다.

    끝까지 검증에 실패해도 예외를 던지지 않고 마지막 결과를 그대로 반환한다.
    완전히 버리는 대신, 부분적으로라도 쓸 수 있는 결과를 보존하기 위해서다.
    """
    validator = VALIDATORS[stage]
    last_result = None
    for attempt in range(1, max_attempts + 1):
        data = generate_fn()
        last_result = data
        if validator(data):
            return data
        print(f"    ⚠️ {stage} 결과가 조건을 만족하지 않음 (시도 {attempt}/{max_attempts}) — 재생성 시도")
    return last_result
