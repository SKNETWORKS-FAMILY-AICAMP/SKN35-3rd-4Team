"""langchain-cli `migrate` 명령이 쓰는 공식 import 치환 패턴을 수집한다.

wheel 안 `langchain_cli/namespaces/migrate/.grit/patterns/`:
    *.json  [[old_path, new_path], ...]
    *.grit  [`old_mod`, `Name`, `new_mod`, `NewName`] 행
pydantic_v1 shim(모듈 단위 치환)은 grit 문법이 달라 직접 추가한다.
"""

import json
import re

from . import CLI_MAPPINGS_PATH, CLI_VERSION
from .extract_symbols import open_wheel, write_jsonl

PATTERN_DIR = "langchain_cli/namespaces/migrate/.grit/patterns/"
GRIT_ROW = re.compile(r"\[\s*`([^`]+)`\s*,\s*`([^`]+)`\s*,\s*`([^`]+)`\s*,\s*`([^`]+)`\s*\]")

# replace_pydantic_v1_shim.grit 내용 (모듈 → 모듈)
PYDANTIC_SHIM = {
    f"{pkg}.pydantic_v1{suffix}": f"pydantic{suffix}"
    for pkg in ("langchain_core", "langchain", "langserve")
    for suffix in ("", ".data_classes", ".main")
}


def main():
    wheel = open_wheel("langchain-cli", CLI_VERSION)
    records: dict[tuple[str, str], dict] = {}

    def add(old: str, new: str, pattern: str, granularity: str = "symbol"):
        records.setdefault((old, new), {"old": old, "new": new, "pattern": pattern, "granularity": granularity})

    for filename in sorted(wheel.namelist()):
        if not filename.startswith(PATTERN_DIR):
            continue
        pattern = filename[len(PATTERN_DIR):]
        text = wheel.read(filename).decode("utf-8")
        if filename.endswith(".json"):
            for old, new in json.loads(text):
                add(old, new, pattern)
        elif filename.endswith(".grit"):
            for old_mod, old_name, new_mod, new_name in GRIT_ROW.findall(text):
                add(f"{old_mod}.{old_name}", f"{new_mod}.{new_name}", pattern)

    for old, new in PYDANTIC_SHIM.items():
        add(old, new, "replace_pydantic_v1_shim.grit", granularity="module")

    out = sorted(records.values(), key=lambda r: (r["old"], r["new"]))
    write_jsonl(CLI_MAPPINGS_PATH, out)
    print(f"langchain-cli=={CLI_VERSION}: {len(out)} mappings")


if __name__ == "__main__":
    main()
