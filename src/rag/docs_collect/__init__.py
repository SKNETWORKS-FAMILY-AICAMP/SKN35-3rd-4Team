"""최신 LangChain(1.x) Python 공식 문서 수집 (2단계).

실행 (프로젝트 루트에서):
    uv run python -m src.rag.docs_collect.fetch_latest_docs

산출물:
    data/raw/docs/latest/{URL 경로}.md     원문 마크다운 (정제는 4단계 청킹에서)
    data/raw/docs/latest_manifest.jsonl   페이지별 url, 섹션, 제목, sha256, 크기, 수집 시각
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
LATEST_DIR = ROOT / "data" / "raw" / "docs" / "latest"
LATEST_MANIFEST_PATH = ROOT / "data" / "raw" / "docs" / "latest_manifest.jsonl"

DOCS_BASE = "https://docs.langchain.com"
PYTHON_INDEX = f"{DOCS_BASE}/_llms/agent-development-lifecycle/build/python.txt"

# 이 접두사로 시작하는 경로만 수집
INCLUDE_PREFIX = "oss/python/"

# LangChain 마이그레이션과 무관한 영역
EXCLUDE_SEGMENTS = {"deepagents", "langgraph", "contributing", "frontend"}
EXCLUDE_NAME_PARTS = ("langgraph", "deepagents")  # migrate/langgraph-v1, reference/langgraph-python 등

# 상세 페이지가 인덱스에 없어서 분류 index의 링크를 따라가 수집하는 통합 분류
INTEGRATION_CATEGORIES = [
    "chat", "embeddings", "vectorstores", "retrievers", "splitters",
    "document_loaders", "tools", "checkpointers", "middleware", "long-term-memory",
]

REQUEST_DELAY_SEC = 0.3
USER_AGENT = "SKN35-4Team-docs-collector/0.1 (LangChain migration RAG study project)"
