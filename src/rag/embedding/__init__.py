"""임베딩 + 벡터DB (5단계).

입력:  data/processed/chunks.jsonl
출력:  data/vectordb/chroma/   (컬렉션 langchain_migration, 코사인 거리)

실행 (프로젝트 루트에서, .env 에 OPENAI_API_KEY 필요):
    uv run python -m src.rag.embedding.build_vectordb
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
VECTORDB_DIR = ROOT / "data" / "vectordb" / "chroma"
ENV_PATH = ROOT / ".env"

COLLECTION_NAME = "langchain_migration"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
DISTANCE = "cosine"

ADD_BATCH_SIZE = 500
MAX_RETRIES = 5
