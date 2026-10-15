# 실무형 질문 36개 (4번 · 평가)

`questions.json`: 실제 사용자가 보낼 법한 **자연어 요청 + 옛 LangChain 코드** 36개 (1.x로 올리기 30 + 버전 오가기 6). 일반 AI와 우리 챗봇을 비교할 때 시험지로 쓰고, 1.x로 올리기 30개는 화면 사이드바의 **확인용 예제**로도 씁니다.

> 2026-10-14: 1번의 그래프 시험 질문(dev `app.py`, ChatOpenAI + LLMChain + PromptTemplate, "양말")과 똑같던 LLMChain 질문 1개를 뺐습니다. 그 자리에 겹치지 않는 새 질문(회의록 요약 체인, `result["text"]` 사용)을 넣어 유형별 3개를 다시 맞췄습니다 (버전 오가기는 q31~q36).

| 필드 | 뜻 |
|---|---|
| `id` · `type` · `difficulty` | q01~q30 (1.x로 올리기), q31~q36 (버전 오가기), 유형(10가지), 쉬움 · 중간 · 어려움 |
| `source_version` · `target_version` | 지금 코드 버전 → 바꿀 버전 (대부분 1.x, 버전 오가기는 0.x로 되돌리기 등) |
| `request` | 사용자 요청 문장 (에러 메시지를 붙인 요청, 일부만 바꿔 달라는 요청 등) |
| `code` | 옛 코드 |
| `expected_imports` | 좋은 답이면 들어 있어야 할 import (1.x는 LangChain 1.4.4에서 실제 import, 0.x는 2번 버전별 도구 목록으로 확인) |
| `checks` | 사람이 볼 점검 항목 (예: `.run( 없음 → invoke`, 대화 기억 유지) |

| 유형 (각 3개) | |
|---|---|
| import 경로 · 문서 로더 · 분할기 · 임베딩 · 벡터스토어 | 경로만 바뀐 경우부터 패키지 설치 안내까지 |
| LLMChain → LCEL · 체인 조합 · RAG | 없어진 체인을 `|`로 다시 짜기 |
| 메모리 · 에이전트 · 도구 | 체크포인터, `create_agent`로 구조 바꾸기 |
| 출력 파서 · 실무 상황 | 구조화 출력, 에러 메시지 설명, 전역 설정, 못 바꾸는 부분 안내 |
| **버전 오가기 (6개)** | 1.x → 0.2 · 0.3 · 0.1 되돌리기, 0.3 → 0.1 · 0.0.354, 0.0.300 → 0.2 중간 단계. 목표 버전에 없는 기능(`create_agent`, `init_chat_model`, `create_tool_calling_agent`, `create_csv_agent`)은 못 바꿈 표시 + 대안 |

난이도: 쉬움 7 · 중간 19 · 어려움 10

**알아 둘 점**: 옛 버전끼리(0.0.300 ↔ 0.3.30)는 자주 쓰는 import 경로가 거의 그대로입니다 (LangChain 이 하위 호환을 유지). 위치가 크게 바뀌는 것은 1.x ↔ 옛 버전, 그리고 나중에 생기거나 없어진 기능입니다.

## 만들기 · 검사

```powershell
python eval/build_questions.py
```

```powershell
python eval/check_questions.py --py <LangChain 1.x python> --map data/processed/import_map.jsonl --symbols data/raw/symbols
```

검사 항목: 옛 코드가 1.x에서 실제로 깨지는가, 기대 import가 1.x에서 되는가(패키지가 없으면 2번 도구 목록으로 확인), 옛 경로가 2번 대응표에 있는가. 목표가 0.x 인 질문은 2번 도구 목록으로 정적 확인(옛 경로가 목표 버전에 없는가, 기대 경로가 목표 버전에 있는가). 2026-10-14 결과 **36/36 통과**.

## 실제 평가 실행 · 채점 (2026-10-15)

| 파일 | 하는 일 |
|---|---|
| `run_eval.py` | 같은 질문을 **우리 챗봇(팀 그래프)** 과 **일반 LLM(gpt-4o-mini, temperature 0, 시스템 프롬프트 없음)** 에 보내고 답을 그대로 저장. 분류기만 3번씩 불러 분류가 흔들리는지도 기록. 끊겨도 다시 실행하면 이어서 |
| `route_probes.json` | 분류 확인 질문 14개 (LangChain 지식 5 · 일반 5 · 지시문 섞기 2 · 코드 변환 2) |
| `score.py` | 저장된 답을 **LLM 없이** 채점 → `results/summary.json`, `results/scorecard.md` |

```powershell
python eval/run_eval.py          # 챗봇 · 일반 LLM · 분류 3회 (질문 50개, 약 30분)
python eval/score.py             # 채점만 (다시 돌리지 않음)
```

- **비교 평가**: 두 답에 같은 잣대(공통 채점 8항목: 문법 · 옛 import · import 존재 · 정의 안 된 이름 · 결과값 보존 · 남은 import · 정답 import · 실제로 바꿈)를 댄다. 일반 LLM 답엔 근거 기록이 없으므로 근거 ID 검사는 넣지 않는다.
- **자체 평가**: 팀이 프롬프트 · 코드에 적어 둔 규칙(분류 · 분석 · 근거 · 고쳐 쓰기 · 검증 · 답변 · 안정성) 21항목을 실행 기록으로 확인해 100점으로 매긴다. 항목별 목표와 미달 질문 번호가 함께 나온다.
