# SKN35-3rd-4Team — LangChain 마이그레이션 RAG 챗봇

구버전 LangChain 코드를 넣으면 **공식 문서와 import 대응표를 근거로** LangChain 1.x(또는 질문에서 지정한 버전) 코드로 바꿔 주는 챗봇입니다.

일반 LLM은 학습 시점의 옛 API를 그대로 답하는 "버전 지체 환각"이 잦습니다. 이 프로젝트는 바꾼 줄마다 근거 ID를 달게 하고, 결과 코드를 정적 검사해 근거 없는 변경이나 존재하지 않는 import가 나오면 다시 검색·재작성합니다.

<div align="center">

![Python](https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white)
![LangChain](https://img.shields.io/badge/LangChain-1.4.5-1C3C3C?logo=langchain&logoColor=white)
![LangGraph](https://img.shields.io/badge/LangGraph-1.2-1C3C3C)
![Streamlit](https://img.shields.io/badge/Streamlit-1.6x-FF4B4B?logo=streamlit&logoColor=white)<br/>
![TiDB](https://img.shields.io/badge/TiDB-Cloud-E30C34)
![Chroma](https://img.shields.io/badge/Chroma-Cloud-F2A33A)

</div>

## 팀원 구성

| | 이름 | 역할 |
| --- | --- | --- |
| <img src="./docs/profile/햄스터.png" width="100" > | 손채영 | 데이터 수집 및 청킹 / Chroma VectorDB 구축 / RAG 검색 Node 정의 / 발표 |
| <img src="./docs/profile/쿼카.png" width="100" > | 심성욱 | 화면 UI 설계 및 구현 / Migration Pipeline 실행 결과 검증 |
| <img src="./docs/profile/가젤.png" width="100" > | 조현주 | 코드 재작성 및 검증 Node 정의 / Migration Pipeline 통합 테스트 |
| <img src="./docs/profile/나무늘보.png" width="100" > | 최우석 | 프로젝트 폴더 구조 정의 / LangGraph 구조 설계 / 질문 분기 및 코드 분석 Node 정의 |

## 주요 기능

- **코드 마이그레이션**: 0.0.x ~ 0.3 코드 → 1.x 변환. 질문에 버전을 적으면 그 버전 기준으로 변환(다운그레이드 포함)
- **근거 기반 변경**: 변경 줄마다 근거 ID·이유 제공, 근거가 부족한 줄은 원문 유지 후 `unresolved`로 안내
- **자동 검증 + 재시도**: 문법, import 존재 여부, 근거 ID, 반환 타입 보존 등을 검사하고 실패 시 최대 3회 재시도
- **설치 패키지 안내**: 새 코드가 쓰는 `langchain-*` 패키지 목록 제공
- **문서 검색 Q&A**: "0.3과 1.0 차이가 뭐야?" 같은 질문은 수집한 문서에서 찾아 답변

## 아키텍처

### 최상위 그래프 (`src/graph/supervisor.py`)

```mermaid
flowchart LR
    START([START]) --> classifier
    classifier -->|migration| migration[[migration 서브그래프]]
    classifier -->|search| search
    classifier -->|general| general
    migration --> END([END])
    search --> END
    general --> END
```

### 마이그레이션 서브그래프 (`src/graph/migration.py`)

```mermaid
flowchart LR
    START([START]) --> analyzer --> retriever --> rewriter --> verifier
    verifier -->|retry| retriever
    verifier -->|done| END([END])
```

### 노드 역할

| 노드 | 파일 | 하는 일 |
|---|---|---|
| classifier | `classifier_node.py` | 질문을 `migration` / `search` / `general`로 분류 |
| analyzer | `analyzer_node.py` | 코드 블록 추출, 바꿔야 할 import·메서드(findings) 분석, 목표 버전(`target_version`) 결정 |
| retriever | `retriever_node.py` | findings별 근거 검색 (대응표 정확매칭 → 하이브리드 문서 검색) |
| rewriter | `rewriter_node.py` | 근거만 사용해 구조화 출력으로 코드 재작성, 변경 내역·설치 패키지 생성 |
| verifier | `verifier_node.py` | 결과 코드 검사. error가 있으면 틀린 근거를 제외하고 retriever로 회귀 |
| search | `search_node.py` | 문서 검색 결과를 근거로 질문에 답변 |
| general | `general_node.py` | 일반 대화 응답 |

**verifier 검사 항목**: 문법 · 근거 ID 유효성 · 변경 기록 일치(기록 없는 변경 = 환각) · 구버전 import 잔존 · 새 import 실존 여부 · 구버전 메서드 잔존 · 안 쓰는 import · 반환값 타입 보존 · 정의 안 된 이름 · LCEL 출력 꺼내기 오류 · 레거시 체인 입출력 키. 최대 시도 횟수는 `VERIFIER_MAX_ATTEMPTS`(기본 3)로 조정합니다.

LLM은 모두 OpenAI `gpt-4o-mini`를 사용합니다.

## RAG 데이터

| 데이터 | 규모 | 설명 |
|---|---|---|
| import 대응표 | 9,155건 | 구버전 경로 → 1.x 경로. PyPI wheel AST 분석(`@deprecated`, `DEPRECATED_LOOKUP` 등) + langchain-cli 마이그레이션 규칙 병합. `native` / `classic_fallback` / `unresolved` 구분 |
| 메서드 대응표 | 42건 | `chain.run` → `invoke` 같은 메서드 변경 (자동 37 + 수동 보강 5) |
| 최신 문서 | 271페이지 | docs.langchain.com Python 문서 (LangGraph·deepagents 섹션 제외) |
| 마이그레이션 가이드 | 24개 | `langchain==0.3.30` 태그의 버전·체인·메모리·에이전트 마이그레이션 문서 |
| 청크 | 11,903개 | 대응표 1건 = 1청크, 문서는 `##`/`###` 단위 분할(최대 4,000자, 코드블록 보존) |
| 벡터DB | Chroma | `text-embedding-3-small`(1536차원), 컬렉션 `langchain_migration` |

### 검색 흐름 (`src/rag/retrieval/`)

1. **대응표 정확매칭**: import 문·메서드 호출을 파싱해 대응표에서 바로 찾음
2. **버전 해석**: 목표 버전이 최신이 아니면 `version_resolve.resolve()`가 대응표 간선을 따라 목표 버전에 존재하는 경로를 찾음 (`keep` / `moved` / `not_available` / `unknown`)
3. **하이브리드 문서 검색**: 벡터 검색 + BM25를 RRF로 합침. 정확매칭된 새 경로로 질의 확장
4. **재정렬**: 0.3 문서 가중치 감소, 목표 import를 쓰는 문서 가중치 증가, 페이지당 최대 2개

## 평가 방법

같은 질문 30개를 **일반 LLM**과 **우리 챗봇**에 넣고 **LLM 없이 코드로** 채점해 비교하고(비교 평가), 팀이 정한 규칙대로 동작하는지 따로 점검합니다(자체 평가).

| 유형 (각 3개) | 쉬움 | 중간 | 어려움 |
|---|---|---|---|
| import 경로 · 문서 로더 · 임베딩 · LLMChain → LCEL · 체인 조합 · RAG · 메모리 · 에이전트 · 출력 파서 · 실무 상황 | 7 | 15 | 8 |

- **질문**: 실제 사용자처럼 "요청 문장 + 옛 코드". 30개 모두 옛 코드가 1.x에서 깨지고 기대 import가 1.x에서 되는지 미리 확인 (36/36, 버전 오가기 6개 포함)
- **공정성**: 양쪽 같은 gpt-4o-mini, temperature 0, 같은 입력. 일반 LLM은 시스템 프롬프트 없이 (ChatGPT에 붙여 넣는 상황). 우리 챗봇만 최대 3회
- **공통 채점 8항목** (두 답에 같은 잣대): 문법 · 옛 import 없음 · import 실제 존재(1.x 도구 목록) · 정의 안 된 이름 없음 · 결과값 보존 · 남은 import 없음 · 정답 import 포함 · 실제로 바꿈 → 8개 모두 통과해야 '공통 기준 통과'
- **자체 평가 21항목 (100점)**: 질문 분류 · 분석 · 근거 검색 · 고쳐 쓰기 규칙 · 검증 루프 · 답변 규칙 · 안정성 (팀 프롬프트 · 코드에 적힌 규칙 그대로)
- 실행: `python eval/run_eval.py` → 채점: `python eval/score.py` (자세히: [eval/README.md](eval/README.md))

## 결과

**실제 실행 사례** (2026-10-14): 0.0.300 `LLMChain` 코드를 화면 경로로 팀 그래프에 보냄 → 두 번 실행해 **두 번 모두 3회차 통과**

```python
# 변경 전                                          # 변경 후 (팀 그래프)
from langchain.chat_models import ChatOpenAI       from langchain_openai import ChatOpenAI
from langchain.prompts import PromptTemplate       from langchain_core.prompts import PromptTemplate
from langchain.chains import LLMChain              from langchain_core.output_parsers import StrOutputParser
chain = LLMChain(llm=llm, prompt=...)              chain = PromptTemplate.from_template(...) | llm | StrOutputParser()
print(chain.run(word='크다'))                       print(chain.invoke({'word': '크다'}))
```

바뀐 6줄 모두 근거 ID(`imap-…`, `mmap-…`, `doc-…`) · 못 바꾼 줄 0 · 한 번 변환에 약 1분

**비교 실험** (2026-10-15, 1.x로 올리기 30개, gpt-4o-mini)

| 항목 | 우리 챗봇 | 일반 LLM |
|---|---|---|
| **공통 기준 통과 (8개 모두)** | **57%** | **0%** |
| 실행 기준 통과 (정답 import 제외) | 87% | 0% |
| 옛 import 없음 | 93% | 3% |
| import가 1.x에 실제로 있음 | 90% | 3% |
| 정답 import 포함 | 60% | 0% |
| 난이도별 (쉬움 · 중간 · 어려움) | 100% · 53% · 25% | 0% · 0% · 0% |
| 응답 시간 (중앙값) | 11.6초 | 3.5초 |

- 일반 LLM은 30개 중 29개에서 옛 import를 그대로 두고 "1.x에 맞게 수정했다"고 답했습니다 (버전 지체 환각 재현)
- 검증 통과: 1회차 43% → 최종 53% · **재시도 효과 +10%p** · 통과한 답 평균 1.2회 · 바뀐 줄의 **93%에 근거 ID**
- 통과 못 한 답은 화면에 '검증 실패'와 이유를 표시 (일반 LLM은 실패를 알리지 않음)
- 버전 오가기 6개(참고): 목표 버전 읽기 100%, 정답 import 0% → 검사기를 목표 버전 기준으로 바꾸는 것이 다음 단계

**자체 평가** 83.3점 / 100 (B) · 21항목 중 13항목 목표 달성

| 영역 | 점수 | | 영역 | 점수 |
|---|---|---|---|---|
| 분석 | 9.8 / 10 | | 질문 분류 | 14.0 / 15 |
| 근거 검색 | 9.9 / 10 | | 고쳐 쓰기 | 22.3 / 25 |
| 답변 규칙 | 5.0 / 5 | | 검증 · 재시도 | 17.3 / 30 |
| 안정성 · 속도 | 5.0 / 5 | | **합계** | **83.3** |

## 폴더 구조

```text
├── streamlit_app.py            # (4번) 화면 입구: 로그인 · 대화 목록 · 진행 표시 · 결과 패널
├── app.py · check_nodes.py     # (1번) 그래프 실행 시험 · (3번) 노드 하나씩 점검
├── src/
│   ├── graph/
│   │   ├── supervisor.py       # (1번) 최상위 그래프: classifier → migration · search · general
│   │   ├── migration.py        # (1번) 변환 파이프라인: analyzer → retriever → rewriter → verifier (재시도)
│   │   ├── state.py            # (3번 · 2번) MigrationState
│   │   └── nodes/              # classifier · general · analyzer (1번) / retriever · search (2번) / rewriter · verifier (3번)
│   ├── prompt/                 # analyzer · classifier · general (1번) / search (2번) / rewriter (3번)
│   ├── rag/                    # (2번) docs_collect · import_map(대응표 · 목표 버전 판정) · chunking · embedding · retrieval
│   └── ui/                     # (4번) client.py(그래프 호출 · 진행 표시) · result_view.py(결과 패널) · db.py(TiDB) · mock.py
├── data/                       # (2번) raw/(문서 · 버전별 도구 목록 42개 · CLI 규칙) · processed/(대응표 · 메서드 대응표 · 청크)
├── eval/                       # (4번) questions.json(36) · route_probes.json(14) · run_eval.py · score.py · results/
├── tools/bot_check.py          # (4번) 화면 · DB 자동 점검 19가지
├── docs/                       # 최종 보고서 · 평가 결과와 개선 방안 · DB 설계 · 화면 실행 방법 · 머지 가이드 · images/
└── 발표자료/                   # 발표 PPT · 대본 · 프로젝트 최종 보고서 · 테스트 · 평가 보고서 · 화면 캡처 · 이전버전/
```

## 시작하기

Python 3.12 이상과 [uv](https://docs.astral.sh/uv/)가 필요합니다.

```bash
uv sync
```

```bash
cp .env.example .env
```

`.env`에 `OPENAI_API_KEY`를 넣습니다.

```bash
uv run python app.py
```

`app.py`의 `question`을 바꿔 다른 코드나 질문을 시험할 수 있습니다. 결과로 변환 코드, 변경 내역(줄·근거 ID·이유), 미해결 항목, 설치 패키지, 검증 결과가 출력됩니다.

노드별로 문제를 확인하려면:

```bash
uv run python check_nodes.py
```

streamlit 실행:

```bash
uv run streamlit run streamlit_app.py
```

## 구현 화면

코드 Migration 결과

<img src="./docs/images/화면_기록/02_배포_예제_검증통과.png"/>