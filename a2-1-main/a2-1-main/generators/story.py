"""
브랜드 스토리 생성 모듈

- 브랜드의 탄생 배경, 철학, 비전을 담은 스토리(300자 내외)를 생성한다.
- 페르소나 힌트, 톤 가드레일, 안티-할루시네이션 가드레일을 프롬프트에 반영한다.
  특히 "탄생 배경" 서술은 모델이 브리프에 없는 구체적 일화나 수치를
  지어낼 위험이 커서, 환각 방지 가드레일이 다른 단계보다 중요하다.
- 결과는 utils.validation.generate_with_validation()을 통해 길이를 검증한 뒤 반환한다.
"""

from utils.llm import call_json_prompt, DEFAULT_MODEL
from utils.prompts import build_persona_hint, TONE_GUARDRAIL_TEMPLATE, ANTI_HALLUCINATION_GUARDRAIL
from utils.validation import generate_with_validation

SYSTEM_PROMPT = """당신은 전문 브랜드 스토리텔러입니다.
반드시 아래 JSON 형식으로만 응답하세요. 다른 설명 문장은 절대 포함하지 마세요.

{
  "story": "브랜드 스토리 본문 (300자 내외, 탄생 배경/철학/비전 포함)"
}"""


def generate_story(api_key: str, brief: dict, model: str = DEFAULT_MODEL) -> str:
    """
    브랜드 스토리를 생성한다.

    Args:
        api_key: Codyssey API 키
        brief: 브랜드 브리프 딕셔너리
        model: 사용할 LLM 모델명

    Returns:
        str: 브랜드 스토리 본문
    """

    def _call():
        user_prompt = f"""업종: {brief['industry']}
타겟: {brief['target']}
페르소나 힌트: {build_persona_hint(brief['target'])}
키워드: {', '.join(brief['keywords'])}
{TONE_GUARDRAIL_TEMPLATE.format(tone=brief.get('tone', '일반적인'))}
추가 요청: {brief.get('notes', '없음')}

{ANTI_HALLUCINATION_GUARDRAIL}

위 브리프와 페르소나를 바탕으로 브랜드의 탄생 배경, 철학, 비전이 담긴
스토리를 300자 내외로 작성해주세요. 브리프에 없는 구체적 연도, 창업자
일화, 수치는 지어내지 말고 일반적인 톤으로 서술하세요."""

        result = call_json_prompt(api_key, SYSTEM_PROMPT, user_prompt, model=model)
        return result.get("story", "")

    return generate_with_validation("story", _call, max_attempts=2)
