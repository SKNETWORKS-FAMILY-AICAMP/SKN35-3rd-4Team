"""1단계 전체 실행: 심볼 추출 → CLI 매핑 수집 → 대응표 병합·import 검증.

    uv run python -m src.rag.import_map.run_all
    uv run python -m src.rag.import_map.run_all --skip-import-check   # 검증 생략 (빠름)
"""

from . import build_import_map, extract_symbols, fetch_cli_mappings


def main():
    print("[1/3] 심볼 추출")
    extract_symbols.main()
    print("[2/3] langchain-cli 매핑 수집")
    fetch_cli_mappings.main()
    print("[3/3] 대응표 병합 + import 검증")
    build_import_map.main()


if __name__ == "__main__":
    main()
