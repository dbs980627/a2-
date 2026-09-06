"""
LLM API 호출 공통 헬퍼

- 각 generators/*.py 모듈이 공통으로 사용하는 "프롬프트 -> JSON 파싱" 로직을 모아둔다.
- Codyssey OpenAI 호환 엔드포인트(/v1/chat/completions)를 requests로 호출한다.
- 모델이 코드블록(```json ... ```)으로 감싸서 응답하는 경우까지 처리한다.
"""

import json
import re
import time          # ← 추가
import requests

BASE_URL = "https://copa.codyssey.kr"
DEFAULT_MODEL = "gpt-5.4-mini"


def call_json_prompt(api_key: str, system_prompt: str, user_prompt: str,
                     model: str = DEFAULT_MODEL, max_retries: int = 4) -> dict:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        "temperature": 0.9,
    }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )

            # 502/503/504 → 서버 일시 과부하. 잠깐 쉬고 재시도
            if response.status_code in (502, 503, 504):
                wait = attempt * 3   # 3초 → 6초 → 9초 (점점 늘림)
                print(f"    ⏳ 서버 혼잡({response.status_code}), "
                      f"{wait}초 후 재시도 ({attempt}/{max_retries})...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            break   # 성공하면 루프 탈출

        except requests.exceptions.RequestException as e:
            last_error = e
            if attempt == max_retries:
                raise RuntimeError(f"LLM API 호출 실패: {e}")
            time.sleep(attempt * 3)
    else:
        # for가 break 없이 끝남 = 계속 502였음
        raise RuntimeError(f"LLM API 호출 실패: {max_retries}회 재시도 후에도 502")

    raw_text = response.json()["choices"][0]["message"]["content"].strip()

    cleaned = re.sub(r"^```(json)?|```$", "", raw_text, flags=re.MULTILINE).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 응답을 JSON으로 파싱하지 못했습니다: {e}\n원본 응답: {raw_text[:300]}")