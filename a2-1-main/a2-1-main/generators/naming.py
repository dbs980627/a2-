"""
브랜드 네이밍 생성 모듈

- 브리프를 기반으로 브랜드명 후보 4개와 각 이름의 의미/유래를 생성한다.
- 페르소나 힌트, 톤 가드레일, 안티-할루시네이션 가드레일을 프롬프트에 반영한다.
- 결과는 utils.validation.generate_with_validation()을 통해 형식/개수를 검증한 뒤 반환한다.
"""

from utils.llm import call_json_prompt, DEFAULT_MODEL
from utils.prompts import build_persona_hint, TONE_GUARDRAIL_TEMPLATE, ANTI_HALLUCINATION_GUARDRAIL
from utils.validation import generate_with_validation

SYSTEM_PROMPT = """당신은 전문 브랜드 네이머입니다.
반드시 아래 JSON 형식으로만 응답하세요. 다른 설명 문장은 절대 포함하지 마세요.

{
  "naming": [
    {"name": "한글 브랜드명", "name_en": "영문 표기", "meaning": "이름의 의미와 유래 (1~2문장)"}
  ]
}

naming 배열에는 정확히 4개의 후보를 담으세요."""


def generate_naming(api_key: str, brief: dict, model: str = DEFAULT_MODEL) -> list:
    """
    브랜드 네이밍 후보를 생성한다.

    Args:
        api_key: Codyssey API 키
        brief: 브랜드 브리프 딕셔너리
        model: 사용할 LLM 모델명

    Returns:
        list[dict]: [{"name", "name_en", "meaning"}, ...]
    """

    def _call():
        user_prompt = f"""업종: {brief['industry']}
타겟: {brief['target']}
페르소나 힌트: {build_persona_hint(brief['target'])}
키워드: {', '.join(brief['keywords'])}
{TONE_GUARDRAIL_TEMPLATE.format(tone=brief.get('tone', '일반적인'))}
경쟁사: {', '.join(brief.get('competitors', [])) or '없음'}
추가 요청: {brief.get('notes', '없음')}

{ANTI_HALLUCINATION_GUARDRAIL}

위 타겟이 자연스럽게 받아들일 언어로, 브리프와 페르소나 힌트에 어울리는
브랜드명 후보를 만들어주세요."""

        result = call_json_prompt(api_key, SYSTEM_PROMPT, user_prompt, model=model)
        return result.get("naming", [])

    return generate_with_validation("naming", _call, max_attempts=2)
