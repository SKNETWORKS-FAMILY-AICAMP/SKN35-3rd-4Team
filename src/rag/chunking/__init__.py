"""청킹 + 메타데이터 (4단계).

입력:
    data/processed/import_map.jsonl         1단계 대응표
    data/processed/method_map.jsonl         1단계 메서드 대응표
    data/raw/docs/latest_manifest.jsonl     2단계 최신 문서
    data/raw/docs/migration_manifest.jsonl  3단계 구버전 마이그레이션 가이드
출력:
    data/processed/chunks.jsonl             전체 청크 (source 필드로 구분)

실행 (프로젝트 루트에서):
    uv run python -m src.rag.chunking.build_chunks
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
IMPORT_MAP_PATH = ROOT / "data" / "processed" / "import_map.jsonl"
METHOD_MAP_PATH = ROOT / "data" / "processed" / "method_map.jsonl"
LATEST_MANIFEST_PATH = ROOT / "data" / "raw" / "docs" / "latest_manifest.jsonl"
MIGRATION_MANIFEST_PATH = ROOT / "data" / "raw" / "docs" / "migration_manifest.jsonl"
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"

# 최신 문서: ##/### 단위로 자르고, 넘치면 문단 단위로 다시 나눈다
MAX_CHARS = 4000
MIN_CHARS = 300

# 구버전 가이드: Legacy ↔ 변경 후 코드가 갈라지지 않도록 크게 자른다
MIGRATION_WHOLE_PAGE_MAX = 8000
MIGRATION_MAX_CHARS = 8000
