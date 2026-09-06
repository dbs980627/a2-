## 1. 시스템 아키텍처

브랜드 브리프를 입력받아 `네이밍 → 슬로건 → 브랜드 스토리 → 컬러 팔레트 → 로고 시안`을
순서대로 생성하는 **파이프라인형 아키텍처**다. `main.py`가 각 단계를 순차 호출하고 결과를
하나의 `result` 딕셔너리에 누적하며, 각 단계는 개별 `try-except`로 감싸여 있어 한 단계가
실패해도 다음 단계로 계속 진행한다.

모듈 구조는 책임 기준으로 나뉜다.

- `generators/naming.py`, `slogan.py`, `story.py`, `color.py`, `logo.py` — 도메인별 생성 로직
- `utils/llm.py` — LLM 호출 공통 헬퍼(`call_json_prompt`), 재시도/즉시실패 분기 포함
- `utils/prompts.py` — 페르소나 힌트, 톤 가드레일, 안티-할루시네이션 가드레일 (공통 상수/함수)
- `utils/validation.py` — 단계별 출력 검증 + 제한적 재생성 루프
- `utils/config.py` — `.env`에서 API 키 로드/검증
- `utils/file_io.py` — 브리프 로드, 출력 폴더 생성, 결과 저장

이 구조를 선택한 이유는, 텍스트 생성 4단계(네이밍/슬로건/스토리/컬러)가 모두 "역할 부여 +
페르소나/톤/환각 가드레일 + JSON 강제 + 검증"이라는 동일한 패턴을 공유하기 때문이다. 이 공통
로직을 `utils/prompts.py`, `utils/validation.py`로 분리해두면, 톤 가드레일 문구나 검증 기준이
바뀌었을 때 한 곳만 고치면 모든 생성 단계에 일괄 반영된다.

---

## 2. 데이터 플로우 및 자료구조

`brief.json`은 `load_brief()`에서 `dict`로 로드되고, 모든 중간 결과는 `main.py`의 `result`
딕셔너리에 누적된다.

```python
result = {
    "brief": brief,
    "naming": [],
    "slogans": [],
    "story": "",
    "color_palette": {},
    "logos": [],
    "errors": [],
    "generated_at": datetime.now().isoformat(timespec="seconds"),
}
```

단계별 실제 입출력:

| 단계 | 함수 | 입력 | 출력 |
|---|---|---|---|
| Brief 로드 | `load_brief(path)` | `brief.json` | `dict` (필수 필드 검증 + 선택 필드 기본값 채움) |
| Naming | `generate_naming(api_key, brief)` | `brief` + 페르소나 힌트 | `list[dict]` (`name`, `name_en`, `meaning`) — 정확히 4개 |
| Slogan | `generate_slogan(api_key, brief)` | `brief` + 페르소나 힌트 | `list[str]` — 정확히 3개 |
| Story | `generate_story(api_key, brief)` | `brief` + 페르소나 힌트 | `str` — 150~500자 |
| Color | `generate_color_palette(api_key, brief, story)` | `brief` + `story` 전체 텍스트 | `dict` (`main`, `sub`, HEX 형식 검증됨) |
| Logo | `build_logo_prompt(brief, naming, palette)` → `generate_logos(...)` | `brief` + `naming[0]` + `palette` | `list[str]` (저장된 PNG 경로) |

**단계 간 체이닝은 여전히 두 곳뿐이다.** Naming·Slogan·Story는 각자 `brief`만 참조하며
서로의 결과를 넘겨받지 않는다 — 슬로건이 확정된 브랜드명을 알지 못한 채로 생성된다는 뜻이다.
실제로 이어지는 지점은 (1) Color가 Story 전체 텍스트를 컨텍스트로 받는 것, (2) Logo가
Naming 1순위 이름과 Color의 메인 컬러명을 받는 것뿐이다. 슬로건/스토리에 네이밍 결과를
컨텍스트로 넘기는 것은 여전히 후속 개선 과제로 남아 있다(7절 참고).

`load_brief()`는 필수 필드(`industry`, `target`, `keywords`)를 검증하고, 선택 필드
(`tone`, `competitors`, `notes`)가 없으면 각각 `""`, `[]`, `""`로 기본값을 채운다.

---

## 3. 상태 관리 및 실패 이력 기록

실행 상태는 메모리 상의 단일 `result` 딕셔너리로 관리된다. 각 단계가 실패하면
`main._record_failure()`가 콘솔 경고 출력과 `result["errors"]` 기록을 동시에 처리한다.

```python
def _record_failure(result: dict, stage: str, error: Exception, message_prefix: str) -> None:
    print(f"  ⚠️ {message_prefix}: {error}")
    result["errors"].append({"stage": stage, "message": str(error)})
```

`errors`는 `{"stage": ..., "message": ...}` 형태의 리스트로 최종 `brand_result.json`에
그대로 저장되므로, 프로그램 실행 후 어떤 단계가 왜 실패했는지 JSON만 보고 사후 분석할 수 있다.
프로그램 종료 시에도 실패한 단계가 있으면 콘솔에 요약 메시지를 한 줄 더 출력한다.

로고 이미지는 `generate_logos()` 내부에서 base64를 디코딩한 직후 PNG로 저장하고, `result`에는
파일 경로 문자열만 남긴다(base64 원본은 메모리에 오래 유지하지 않음).

---

## 4. 예외 처리 및 재시도 정책 (`utils/llm.py`)

`call_json_prompt()`가 모든 텍스트 생성 단계의 LLM 호출을 담당한다.

- **400/401/403 (`FATAL_STATUS`)**: 재시도로 해결되지 않는 오류이므로 **즉시 `RuntimeError`를
  던지고 재시도하지 않는다.**
- **502/503/504 (`RETRYABLE_STATUS`)**: 서버 일시 과부하로 간주해 재시도한다. 대기 시간은
  `attempt * 3`초로 **선형 증가**한다(3초 → 6초 → 9초). `max_retries`(기본 4회) 안에
  성공하지 못하면 `RuntimeError`를 던진다.
- **그 외 requests 예외**(타임아웃, 연결 오류, 그리고 `FATAL_STATUS`·`RETRYABLE_STATUS`에
  속하지 않는 상태 코드에서 `raise_for_status()`가 던지는 `HTTPError` 포함): 마지막 시도가
  아니면 동일하게 `attempt * 3`초 대기 후 재시도, 마지막 시도면 `RuntimeError`로 변환해 던진다.
- **JSON 파싱 실패**: 코드블록 기호(` ```json `)를 정규식으로 제거한 뒤 `json.loads()`를
  시도하고, 실패하면 `ValueError`로 원본 응답 일부(300자)와 함께 던진다.

```python
RETRYABLE_STATUS = (502, 503, 504)
FATAL_STATUS = (400, 401, 403)

for attempt in range(1, max_retries + 1):
    try:
        response = requests.post(...)

        if response.status_code in FATAL_STATUS:
            raise RuntimeError(
                f"LLM API 호출 실패(재시도 불가): HTTP {response.status_code} "
                f"- {response.text[:200]}"
            )

        if response.status_code in RETRYABLE_STATUS:
            wait = attempt * 3
            time.sleep(wait)
            continue

        response.raise_for_status()
        break

    except RuntimeError:
        # FATAL_STATUS에서 위로 던진 RuntimeError는 재시도 경로를 타지 않고 그대로 전파한다.
        raise

    except requests.exceptions.RequestException as e:
        if attempt == max_retries:
            raise RuntimeError(f"LLM API 호출 실패: {e}")
        time.sleep(attempt * 3)
else:
    # for가 break 없이 끝남 = 계속 RETRYABLE_STATUS였음
    raise RuntimeError(f"LLM API 호출 실패: {max_retries}회 재시도 후에도 서버 오류")
```

`except RuntimeError: raise` 분기를 별도로 둔 이유: `FATAL_STATUS`에서 던진 `RuntimeError`는
`requests.exceptions.RequestException`의 하위 클래스가 아니라서 바로 아래 `except` 절에
잡히지는 않지만, 두 `except` 절의 의도(재시도 불가 vs 재시도 가능)를 코드 구조로도 명확히
드러내고 향후 예외 계층이 바뀌어도 FATAL 경로가 실수로 재시도 경로에 섞이지 않도록 명시적으로
분리해뒀다.

이전 버전에서는 `raise_for_status()`가 던지는 `HTTPError`가 `RequestException`의 하위
클래스라는 이유로 401/403도 502/503/504와 같은 재시도 경로를 탔다. 인증 실패나 잘못된 요청은
몇 번을 다시 호출해도 결과가 같으므로, 상태 코드 체크 순서를 `FATAL_STATUS` → `RETRYABLE_STATUS`
→ 그 외(`raise_for_status()`) 순으로 재배치해 즉시 실패 경로를 분리했다.

`main.py`는 `RuntimeError`/`ValueError` 두 타입만 잡도록 설계돼 있어 위 정책과 정확히
맞물린다.

그 외 예외 처리:

- **브리프 파일 오류** (`utils/file_io.py`): 파일이 없으면 `FileNotFoundError`, JSON 파싱
  실패나 필수 필드 누락이면 `ValueError`를 던진다. `main.py`는 이를 잡아 메시지를 출력하고
  즉시 종료한다(재시도 없음, 정상 종료).
- **API 키 미설정** (`utils/config.py`): `.env`에 `COPA_API_KEY`가 없으면
  `validate_api_keys()`가 설정 방법 3단계 안내를 직접 출력하고 `False`를 반환하며, `main.py`는
  이를 받아 즉시 종료한다.
- **로고 생성 실패**: `generate_logos()` 내부에서 이미지 1장 단위로 개별 `try-except`가 있어,
  2장 중 1장만 실패해도 나머지 1장은 저장되고 성공한 경로만 리스트에 남는다. `main.py`는 이
  호출 전체를 넓은 `except Exception`으로 한 번 더 감싸고, 이 역시 `result["errors"]`에
  `stage: "logo"`로 기록된다.

---

## 5. 프롬프트 엔지니어링 원칙

모든 텍스트 생성 모듈(`naming`, `slogan`, `story`, `color`)은 같은 4단 구조를 프롬프트에 쌓는다.

1. **역할 부여**: "브랜드 네이머" / "카피라이터" / "브랜드 스토리텔러" / "컬러 컨설턴트"로
   시스템 프롬프트에서 역할 고정.
2. **페르소나/컨텍스트 주입**: 업종, 타겟, 키워드, 톤, 경쟁사, 이전 단계 결과(컬러 단계의
   `story`)를 유저 프롬프트에 포함. (아래 6절 참고)
3. **제약조건 명시**: 후보 개수(네이밍 4개, 슬로건 3개), 길이(스토리 300자 내외), 형식(HEX
   코드), 금지 표현(톤 가드레일)을 명시.
4. **출력 형식 강제**: 시스템 프롬프트 안에 JSON 스키마를 예시로 포함하고 "다른 설명 문장은
   절대 포함하지 마세요"라고 명시. 컬러 단계는 `#RRGGBB` 형식 예시까지 포함 — 이는 창작
   다양성을 제한하는 내용 예시가 아니라 순수한 형식 예시이므로, 퓨샷을 최소화하는 원칙과
   배치되지 않는다.

---

## 6. 페르소나 반영 방식 (`utils/prompts.py`)

타겟 문자열을 그대로 프롬프트에 삽입하는 대신, 연령대 힌트를 감성/언어 톤 축으로 변환하는
`build_persona_hint()`를 거쳐 주입한다.

```python
def build_persona_hint(target: str) -> str:
    hints = {
        "10": "또래 문화, 유행 민감도, 짧고 강한 임팩트를 우선 고려",
        "20": "감성적 친밀감, 자기표현 욕구, SNS 공유 가능성을 우선 고려",
        "30": "실용성과 신뢰, 효율적인 문제 해결을 우선 고려",
        "40": "안정감, 품질에 대한 확신, 과장되지 않은 신뢰를 우선 고려",
        "50": "전통적 가치, 편안함, 검증된 안정성을 우선 고려",
    }
    matched = [v for key, v in hints.items() if key in target]
    return " / ".join(matched) if matched else "타겟의 일반적인 관심사와 언어 습관을 우선 고려"
```

`naming.py`, `slogan.py`, `story.py`는 이 함수의 결과를 "페르소나 힌트" 항목으로 유저 프롬프트에
포함한다. 타겟이 "20~30대 여성"처럼 여러 연령대를 포함하면 해당 힌트들이 함께 반환된다. 브리프에
없는 새로운 사실(연령대별 소비 데이터 등)을 만들어내지 않고, 일반적으로 통용되는 세그먼트 특성만
힌트로 제공하도록 제한했다. 컬러 단계는 언어 톤이 아니라 시각 요소를 다루므로 페르소나 힌트를
적용하지 않았다.

---

## 7. 톤앤매너 강제 방식 (`TONE_GUARDRAIL_TEMPLATE`)

`tone` 필드는 모든 텍스트 생성 단계에서 공통 가드레일 문구로 프롬프트에 삽입된다.

```python
TONE_GUARDRAIL_TEMPLATE = (
    "톤앤매너: {tone}\n"
    "다음 표현은 사용하지 마세요: 과장된 최상급 표현(최고, 완벽, No.1), "
    "공격적이거나 자극적인 슬랭, 근거 없는 효능 단정.\n"
    "위 톤과 어긋나는 후보는 생성하지 말고, 톤에 맞는 후보만 제시하세요."
)
```

이 문구를 네이밍·슬로건·스토리·컬러 네 단계에서 동일하게 재사용해, 단계마다 톤 표현이 미묘하게
달라져 브랜드 일관성이 깨지는 것을 방지했다. 컬러 단계에서는 여기에 더해 "톤앤매너와 어긋나는
채도/명도 조합은 제외하세요"라는 문장을 추가로 붙여, 텍스트 톤과 시각 톤이 어긋나지 않도록 했다.

---

## 8. 환각 제어 및 제약조건 설계 (`ANTI_HALLUCINATION_GUARDRAIL`)

모든 텍스트 생성 프롬프트 끝에 공통 안티-할루시네이션 가드레일을 붙인다.

```python
ANTI_HALLUCINATION_GUARDRAIL = (
    "아래 조건을 반드시 지키세요.\n"
    "1. 브리프에 명시되지 않은 시장 점유율, 매출, 소비자 반응 등 구체적 수치를 언급하지 마세요.\n"
    "2. 경쟁사 정보는 차별화 방향을 설명하는 데만 참고하고, 경쟁사에 대한 사실 단정은 하지 마세요.\n"
    "3. 상표 등록 가능 여부나 법적 판단을 내리지 마세요. 이는 창작 아이디어 제안일 뿐입니다.\n"
    "4. 요청된 JSON 형식 외의 설명, 서론, 마크다운 코드블록 기호를 출력하지 마세요."
)
```

특히 브랜드 스토리(`generate_story`)는 "탄생 배경"을 서술하는 특성상 모델이 구체적인 창업
연도나 일화를 지어낼 위험이 커서, 유저 프롬프트에 "브리프에 없는 구체적 연도, 창업자 일화,
수치는 지어내지 말고 일반적인 톤으로 서술하세요"라는 문장을 별도로 추가했다.

퓨샷 예시는 결과 다양성을 제한할 수 있어 기본적으로 사용하지 않는다. 다만 출력 형식이 모호해질
위험이 있는 컬러 단계에서만 `#RRGGBB` 형식 예시를 스키마 설명용으로 포함한다 — 이는 순수한 형식
예시이지 창작 방향을 좁히는 내용 예시가 아니다.

---

## 9. 출력 검증 및 셀프 리파인 (`utils/validation.py`)

각 생성 결과는 `generate_with_validation(stage, generate_fn, max_attempts)`을 통해 형식/개수/
길이를 검증한 뒤 반환된다.

```python
def generate_with_validation(stage, generate_fn, max_attempts=2):
    validator = VALIDATORS[stage]
    last_result = None
    for attempt in range(1, max_attempts + 1):
        data = generate_fn()
        last_result = data
        if validator(data):
            return data
        print(f"    ⚠️ {stage} 결과가 조건을 만족하지 않음 (시도 {attempt}/{max_attempts}) — 재생성 시도")
    return last_result
```

단계별 검증 기준:

- **네이밍**: 정확히 4개 + 필수 필드(`name`, `name_en`, `meaning`) 존재
- **슬로건**: 정확히 3개 + 각 문장 길이 5~40자
- **스토리**: 150~500자 (프롬프트의 "300자 내외" 요구에 여유를 둠)
- **컬러 팔레트**: `main`/`sub` 키 존재, HEX 형식(`#RRGGBB`) 유효성, `sub` 2~3개

`generate_fn()` 내부에서 `RuntimeError`/`ValueError`(LLM 호출 실패, JSON 파싱 실패)가 발생하면
이 루프는 그 예외를 잡지 않고 그대로 상위(`generate_naming()` 등)로 전달한다. 이 함수는
"형식은 왔지만 조건을 어긴" 응답만 다루며, API/파싱 실패는 4절의 예외 처리 경로를 그대로 타도록
분리했다. 검증에 끝까지 실패해도 예외를 던지지 않고 마지막 결과를 그대로 반환한다 — 완전히
버리는 대신 부분적으로라도 쓸 수 있는 결과를 보존하기 위해서다.

별도의 복잡한 평가 모델을 두기보다 "형식 검증 + 조건 불일치 시 제한적 재생성(최대 2회)" 구조를
선택한 것은, 구현 복잡도와 실용성 사이의 균형을 고려한 결정이다.

---

## 10. 왜 이렇게 구현했는가

현재 구현은 **단일 파이프라인 + 단계별 책임 분리 + 공통 가드레일/검증 모듈**을 선택했다.
`utils/prompts.py`와 `utils/validation.py`로 페르소나·톤·환각 제어·검증 로직을 분리해둔
이유는, 이 로직이 네이밍·슬로건·스토리·컬러 네 단계에서 거의 동일하게 반복되기 때문이다.
공통 모듈로 빼두면 가드레일 문구나 검증 기준이 바뀌었을 때 각 `generators/*.py`를 일일이
수정할 필요 없이 한 곳만 고치면 된다.

`utils/llm.py`에 재시도/즉시실패 로직을 모아둔 것도 같은 이유다 — 모든 텍스트 생성 단계가
동일한 안정성 정책(즉시실패 대상과 재시도 대상의 구분)을 공유하게 된다.

`result["errors"]`에 실패 이력을 남기는 방식을 선택한 이유는, 이 프로그램이 대화형 CLI로
한 번 실행하고 끝나는 게 아니라 결과 JSON을 이후에도 참조할 수 있어야 하기 때문이다. 콘솔
로그는 실행이 끝나면 사라지지만, JSON에 남은 `errors`는 어떤 단계가 왜 실패했는지 나중에도
확인할 수 있다.

여전히 남아있는 한계와 후속 개선 방향:

- 슬로건/스토리 단계에 네이밍 결과를 컨텍스트로 주입해 브랜드명과의 언어적 일관성 확보
- 검증 실패 시 재생성 횟수를 브리프 복잡도에 따라 동적으로 조절
- `errors` 기록을 단순 문자열이 아니라 `retry_count`, `http_status` 등 구조화된 필드로 확장
