"""검색 엔진 (5단계, 실행 순서).

흐름:
    ① import 대응표 정확매칭 (import 문/경로 → imap-… 근거)
    ② 메서드 대응표 정확매칭 (메서드 호출 → mmap-… 근거, 근거 문서 페이지 doc_refs 수집)
    ③ ①에서 못 찾은 경로만 대응표 유사 검색 (같은 1.x 경로는 하나로)
    ④ 문서 하이브리드 검색: 벡터(Chroma) + BM25, RRF 로 순위 융합
       (①의 1.x 경로·대안으로 질의 확장, ②의 doc_refs 페이지 청크는 상위권 점수로)
    ⑤ 규칙 기반 재정렬 (최신 문서 우선, 정답 import 를 쓰는 문서 가산, 페이지당 개수 제한)

목표 버전(target_version)이 최신이 아니면 ①을 version_resolve로 판정하고(③ 생략),
②는 목표 버전에서 이미 deprecated인 메서드만, ⑤는 목표가 0.x면 0.3 문서를 우선한다.

터미널에서 바로 질의:
    uv run python -m src.rag.retrieval.hybrid "from langchain.chains import LLMChain"
    uv run python -m src.rag.retrieval.hybrid "memory for chat history" --old langchain.memory.ConversationBufferMemory
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IMPORT_MAP_PATH = ROOT / "data" / "processed" / "import_map.jsonl"
METHOD_MAP_PATH = ROOT / "data" / "processed" / "method_map.jsonl"
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"

DOC_SOURCES = ("latest_docs", "migration_guide")

DEFAULT_K = 5              # 반환할 문서 근거 수
CANDIDATES = 30            # 벡터·BM25 각각에서 가져올 후보 수
RRF_K = 60                 # Reciprocal Rank Fusion 상수
FUZZY_MAP_K = 3            # 정확매칭 실패 시 대응표 유사 후보 수
MAX_PER_PAGE = 2           # 같은 페이지 청크 최대 개수

ERA_WEIGHT = {"1.x": 1.0, "0.3": 0.8}   # 구버전 가이드는 "변경 후" 코드가 0.3 기준
ERA_WEIGHT_0X = {"1.x": 0.8, "0.3": 1.0}  # 목표가 0.x(다운그레이드)면 0.3 기준 가이드를 우선
IMPORT_LINK_BOOST = 1.5                  # 정확매칭된 1.x import 를 실제로 쓰는 청크 가산
DOC_REF_BOOST = 2.0                      # 메서드 대응표가 근거로 지정한 문서 페이지 가산

BM25_K1 = 1.5
BM25_B = 0.75
