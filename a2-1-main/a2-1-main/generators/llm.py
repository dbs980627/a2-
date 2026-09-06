"""
LLM API 호출 공통 헬퍼

- 각 generators/*.py 모듈이 공통으로 사용하는 "프롬프트 -> JSON 파싱" 로직을 모아둔다.
- Codyssey OpenAI 호환 엔드포인트(/v1/chat/completions)를 requests로 호출한다.
- 모델이 코드블록(```json ... ```)으로 감싸서 응답하는 경우까지 처리한다.

재시도 정책:
- RETRYABLE_STATUS(502/503/504): 서버 일시 과부하로 간주, 선형 백오프 후 재시도.
- FATAL_STATUS(400/401/403): 재시도로 해결되지 않는 오류이므로 즉시 실패 처리한다.
  (이전 버전에서는 이 오류들이 RequestException 경로를 그대로 타서 불필요하게
  재시도됐다 — 잘못된 요청/인증 실패는 몇 번을 다시 불러도 결과가 같기 때문에
  이번에 분리했다.)
"""

import json
import re
import time
import requests

BASE_URL = "https://copa.codyssey.kr"
DEFAULT_MODEL = "gpt-5.4-mini"

RETRYABLE_STATUS = (502, 503, 504)
FATAL_STATUS = (400, 401, 403)


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

    for attempt in range(1, max_retries + 1):
        try:
            response = requests.post(
                f"{BASE_URL}/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=60,
            )

            # 400/401/403 → 재시도로 해결되지 않는 오류. 즉시 실패 처리.
            if response.status_code in FATAL_STATUS:
                raise RuntimeError(
                    f"LLM API 호출 실패(재시도 불가): HTTP {response.status_code} "
                    f"- {response.text[:200]}"
                )

            # 502/503/504 → 서버 일시 과부하. 잠깐 쉬고 재시도
            if response.status_code in RETRYABLE_STATUS:
                wait = attempt * 3   # 3초 → 6초 → 9초 (선형 증가)
                print(f"    ⏳ 서버 혼잡({response.status_code}), "
                      f"{wait}초 후 재시도 ({attempt}/{max_retries})...")
                time.sleep(wait)
                continue

            response.raise_for_status()
            break   # 성공하면 루프 탈출

        except RuntimeError:
            # FATAL_STATUS에서 위로 던진 RuntimeError는 재시도하지 않고 그대로 전파한다.
            raise

        except requests.exceptions.RequestException as e:
            if attempt == max_retries:
                raise RuntimeError(f"LLM API 호출 실패: {e}")
            time.sleep(attempt * 3)
    else:
        # for가 break 없이 끝남 = 계속 502/503/504였음
        raise RuntimeError(f"LLM API 호출 실패: {max_retries}회 재시도 후에도 서버 오류")

    raw_text = response.json()["choices"][0]["message"]["content"].strip()

    cleaned = re.sub(r"^```(json)?|```$", "", raw_text, flags=re.MULTILINE).strip()

    try:
        return json.loads(cleaned)
    except json.JSONDecodeError as e:
        raise ValueError(f"LLM 응답을 JSON으로 파싱하지 못했습니다: {e}\n원본 응답: {raw_text[:300]}")
