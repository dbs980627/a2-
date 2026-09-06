"""
컬러 팔레트 생성 및 시각화 모듈

- LLM에게 브랜드에 어울리는 메인/서브 컬러를 HEX 코드로 추천받는다.
- matplotlib으로 팔레트를 시각화하여 PNG로 저장한다.
- 브랜드 스토리를 함께 컨텍스트로 넘겨, 앞서 생성된 톤과 일관된 컬러가 나오도록 한다.
- 톤 가드레일과 안티-할루시네이션 가드레일을 프롬프트에 반영한다.
  (페르소나 힌트는 언어 톤을 위한 것이라 색상 추천에는 적용하지 않았다.)
- 결과는 utils.validation.generate_with_validation()을 통해 HEX 형식/개수를 검증한 뒤 반환한다.
"""

import os
import matplotlib
matplotlib.use("Agg")  # GUI 없는 환경에서도 이미지 저장 가능하도록 설정
import matplotlib.pyplot as plt

from utils.llm import call_json_prompt, DEFAULT_MODEL
from utils.prompts import TONE_GUARDRAIL_TEMPLATE, ANTI_HALLUCINATION_GUARDRAIL
from utils.validation import generate_with_validation

SYSTEM_PROMPT = """당신은 전문 브랜드 컬러 컨설턴트입니다.
반드시 아래 JSON 형식으로만 응답하세요. 다른 설명 문장은 절대 포함하지 마세요.

{
  "main": {"hex": "#RRGGBB", "name": "컬러 이름(영문)"},
  "sub": [
    {"hex": "#RRGGBB", "name": "컬러 이름(영문)"},
    {"hex": "#RRGGBB", "name": "컬러 이름(영문)"}
  ]
}

sub 배열에는 2~3개의 서브 컬러를 담으세요. 반드시 유효한 6자리 HEX 코드를 사용하세요."""


def generate_color_palette(api_key: str, brief: dict, story: str = "", model: str = DEFAULT_MODEL) -> dict:
    """
    브랜드 컬러 팔레트를 생성한다.

    Args:
        api_key: Codyssey API 키
        brief: 브랜드 브리프 딕셔너리
        story: 앞서 생성된 브랜드 스토리 (컬러 추천의 일관성을 위한 컨텍스트)
        model: 사용할 LLM 모델명

    Returns:
        dict: {"main": {"hex", "name"}, "sub": [{"hex", "name"}, ...]}
    """

    def _call():
        user_prompt = f"""업종: {brief['industry']}
타겟: {brief['target']}
키워드: {', '.join(brief['keywords'])}
{TONE_GUARDRAIL_TEMPLATE.format(tone=brief.get('tone', '일반적인'))}
브랜드 스토리: {story or '없음'}

{ANTI_HALLUCINATION_GUARDRAIL}

위 브랜드에 어울리는 메인 컬러 1개와 서브 컬러 2~3개를 HEX 코드로 추천해주세요.
톤앤매너와 어긋나는 채도/명도 조합(예: 따뜻한 톤인데 차갑고 채도가 지나치게
높은 색)은 제외하세요."""

        return call_json_prompt(api_key, SYSTEM_PROMPT, user_prompt, model=model)

    return generate_with_validation("color", _call, max_attempts=2)


def visualize_palette(palette: dict, output_dir: str) -> str:
    """
    컬러 팔레트를 가로 스와치(swatch) 형태로 시각화하여 PNG로 저장한다.

    Args:
        palette: generate_color_palette()가 반환한 딕셔너리
        output_dir: 저장할 폴더 경로

    Returns:
        str: 저장된 PNG 파일 경로
    """
    main = palette.get("main", {})
    subs = palette.get("sub", [])
    colors = [main] + subs  # 메인 컬러를 맨 앞에 배치

    fig, ax = plt.subplots(figsize=(2.2 * len(colors), 3))

    for i, color in enumerate(colors):
        hex_code = color.get("hex", "#CCCCCC")
        name = color.get("name", "")
        label = "MAIN" if i == 0 else "SUB"

        ax.add_patch(plt.Rectangle((i, 0), 1, 1, color=hex_code))
        ax.text(i + 0.5, -0.15, f"{label}\n{hex_code}\n{name}",
                ha="center", va="top", fontsize=9)

    ax.set_xlim(0, len(colors))
    ax.set_ylim(-0.6, 1)
    ax.axis("off")
    ax.set_title("Brand Color Palette", fontsize=13, pad=10)

    output_path = os.path.join(output_dir, "color_palette.png")
    plt.savefig(output_path, bbox_inches="tight", dpi=150)
    plt.close(fig)

    return output_path
