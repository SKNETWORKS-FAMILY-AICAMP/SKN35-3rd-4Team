"""버전별 import 대응표 (1단계).

구버전 LangChain import 경로 → 1.x 경로 대응표를 PyPI wheel 정적 분석으로 만든다.

실행 (프로젝트 루트에서):
    uv run python -m src.rag.import_map.run_all

산출물:
    data/raw/symbols/{패키지}-{버전}.jsonl   패키지·버전별 심볼 목록
    data/raw/cli_mappings.jsonl             langchain-cli migrate 매핑
    data/processed/import_map.jsonl         최종 대응표 (레코드마다 고정 id)
    data/processed/method_map.jsonl         메서드 대응표 (chain.run() → invoke 등)
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
RAW_DIR = ROOT / "data" / "raw"
SYMBOLS_DIR = RAW_DIR / "symbols"
CLI_MAPPINGS_PATH = RAW_DIR / "cli_mappings.jsonl"
IMPORT_MAP_PATH = ROOT / "data" / "processed" / "import_map.jsonl"
METHOD_MAP_PATH = ROOT / "data" / "processed" / "method_map.jsonl"

# 구버전: 사용자 코드에 등장할 수 있는 경로의 출처
OLD_VERSIONS: dict[str, list[str]] = {
    "langchain": ["0.0.300", "0.0.354", "0.1.20", "0.2.17", "0.3.30"],
    "langchain-core": ["0.1.53", "0.2.43", "0.3.86"],
    "langchain-community": ["0.0.38", "0.2.19", "0.3.31"],
}

# 대상(1.x): 변환 결과가 실제로 존재해야 하는 버전
TARGET_VERSIONS: dict[str, str] = {
    "langchain": "1.4.5",
    "langchain-core": "1.6.10",
    "langchain-classic": "1.0.8",
    "langchain-community": "0.4.2",
    "langchain-text-splitters": "1.1.3",
    "langchain-openai": "1.7.1",
    "langchain-anthropic": "1.7.6",
    "langchain-ollama": "1.1.0",
    "langchain-huggingface": "1.2.3",
    "langchain-google-genai": "4.4.1",
    "langchain-chroma": "1.1.0",
    "langgraph": "1.2.14",
}

# 버전 변경 목표: langchain 마이너마다 마지막 패치 1개를 대표로 두고, 짝 패키지는
# 그 langchain 출시일 기준 최신 릴리스. 사용자가 말한 버전은 같은 마이너 대표로 맞춘다.
# 0.x 대표는 이미 추출해 둔 OLD_VERSIONS 안에서 가장 가까운 버전.
VERSION_SETS: dict[str, dict[str, str]] = {
    "0.0.300": {"langchain": "0.0.300"},
    "0.0.354": {"langchain": "0.0.354", "langchain-core": "0.1.53", "langchain-community": "0.0.38"},
    "0.1.20": {"langchain": "0.1.20", "langchain-core": "0.1.53", "langchain-community": "0.0.38"},
    "0.2.17": {"langchain": "0.2.17", "langchain-core": "0.2.43", "langchain-community": "0.2.19",
               "langchain-text-splitters": "0.2.4"},
    "0.3.30": {"langchain": "0.3.30", "langchain-core": "0.3.86", "langchain-community": "0.3.31",
               "langchain-text-splitters": "0.3.11"},
    "1.0.8": {"langchain": "1.0.8", "langchain-core": "1.0.6", "langgraph": "1.0.3",
              "langchain-classic": "1.0.0", "langchain-community": "0.4.1", "langchain-text-splitters": "1.0.0"},
    "1.1.3": {"langchain": "1.1.3", "langchain-core": "1.1.2", "langgraph": "1.0.4",
              "langchain-classic": "1.0.0", "langchain-community": "0.4.1", "langchain-text-splitters": "1.0.0"},
    "1.2.18": {"langchain": "1.2.18", "langchain-core": "1.3.3", "langgraph": "1.1.10",
               "langchain-classic": "1.0.7", "langchain-community": "0.4.1", "langchain-text-splitters": "1.1.2"},
    "1.3.18": {"langchain": "1.3.18", "langchain-core": "1.6.0", "langgraph": "1.2.11",
               "langchain-classic": "1.0.8", "langchain-community": "0.4.2", "langchain-text-splitters": "1.1.2"},
    "1.4.5": {"langchain": "1.4.5", "langchain-core": "1.6.10", "langgraph": "1.2.14",
              "langchain-classic": "1.0.8", "langchain-community": "0.4.2", "langchain-text-splitters": "1.1.3"},
}
LATEST_VERSION = "1.4.5"

CLI_VERSION = "0.0.37"
PYTHON_VERSION = "3.12"


def symbols_path(package: str, version: str) -> Path:
    return SYMBOLS_DIR / f"{package}-{version}.jsonl"
