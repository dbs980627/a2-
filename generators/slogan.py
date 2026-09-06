"""
슬로건/태그라인 생성 모듈

- 브리프의 톤앤매너에 맞는 슬로건 3개를 생성한다.
- 페르소나 힌트, 톤 가드레일, 안티-할루시네이션 가드레일을 프롬프트에 반영한다.
- 결과는 utils.validation.generate_with_validation()을 통해 개수/길이를 검증한 뒤 반환한다.
"""

from utils.llm import call_json_prompt, DEFAULT_MODEL
from utils.prompts import build_persona_hint, TONE_GUARDRAIL_TEMPLATE, ANTI_HALLUCINATION_GUARDRAIL
from utils.validation import generate_with_validation

SYSTEM_PROMPT = """당신은 전문 카피라이터입니다.
반드시 아래 JSON 형식으로만 응답하세요. 다른 설명 문장은 절대 포함하지 마세요.

{
  "slogans": ["슬로건1", "슬로건2", "슬로건3"]
}

slogans 배열에는 정확히 3개의 짧고 임팩트 있는 문구를 담으세요."""


def generate_slogan(api_key: str, brief: dict, model: str = DEFAULT_MODEL) -> list:
    """
    브랜드 슬로건 3개를 생성한다.

    Args:
        api_key: Codyssey API 키
        brief: 브랜드 브리프 딕셔너리
        model: 사용할 LLM 모델명

    Returns:
        list[str]: 슬로건 3개
    """

    def _call():
        user_prompt = f"""업종: {brief['industry']}
타겟: {brief['target']}
페르소나 힌트: {build_persona_hint(brief['target'])}
키워드: {', '.join(brief['keywords'])}
{TONE_GUARDRAIL_TEMPLATE.format(tone=brief.get('tone', '일반적인'))}

{ANTI_HALLUCINATION_GUARDRAIL}

위 브리프와 페르소나에 어울리는 슬로건/태그라인을 만들어주세요."""

        result = call_json_prompt(api_key, SYSTEM_PROMPT, user_prompt, model=model)
        return result.get("slogans", [])

    return generate_with_validation("slogan", _call, max_attempts=2)
