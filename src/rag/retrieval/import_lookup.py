"""import 문 파싱 + 대응표 정확매칭.

    from langchain.chat_models import ChatOpenAI as Chat  → langchain.chat_models.ChatOpenAI
    from x import (a, b)                                   → x.a, x.b
    import langchain_core.pydantic_v1                      → langchain_core.pydantic_v1 (모듈)
모듈 단위 매핑(pydantic_v1 → pydantic)은 대응표에 없는 이름도 모듈 레코드로 치환한다.
"""

import json
import re
from dataclasses import dataclass
from functools import lru_cache

from . import IMPORT_MAP_PATH

FROM_IMPORT = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+(\([^)]*\)|[^\n#]+)", re.MULTILINE)
PLAIN_IMPORT = re.compile(r"^\s*import\s+([\w.]+(?:\s+as\s+\w+)?(?:\s*,\s*[\w.]+(?:\s+as\s+\w+)?)*)", re.MULTILINE)
DOTTED_PATH = re.compile(r"^[A-Za-z_]\w*(\.[A-Za-z_]\w*)+$")


@dataclass(frozen=True)
class MapHit:
    query_path: str        # 사용자 코드의 경로
    record: dict           # import_map.jsonl 레코드
    via_module: bool       # 모듈 단위 매핑으로 치환했는지

    @property
    def new(self) -> str | None:
        if self.via_module and self.record["new"]:
            name = self.query_path[len(self.record["old"]):]
            return self.record["new"] + name
        return self.record["new"]


def parse_import_paths(text: str) -> list[str]:
    """import 문(여러 줄 가능) 또는 점 경로에서 langchain 계열 경로를 뽑는다."""
    text = text.strip()
    if DOTTED_PATH.match(text):
        return [text]
    paths = []
    for module, names in FROM_IMPORT.findall(text):
        for name in names.strip("()").replace("\n", " ").split(","):
            name = name.strip().split(" as ")[0].strip()
            if name and name != "*":
                paths.append(f"{module}.{name}")
    for group in PLAIN_IMPORT.findall(text):
        for item in group.split(","):
            paths.append(item.strip().split(" as ")[0].strip())
    return [p for p in dict.fromkeys(paths) if p.startswith(("langchain", "langgraph"))]


@lru_cache(maxsize=1)
def _load() -> tuple[dict[str, dict], dict[str, dict]]:
    symbols, modules = {}, {}
    with IMPORT_MAP_PATH.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            (modules if rec["granularity"] == "module" else symbols)[rec["old"]] = rec
    return symbols, modules


def lookup(path: str) -> MapHit | None:
    symbols, modules = _load()
    if path in symbols:
        return MapHit(path, symbols[path], via_module=False)
    if path in modules:
        return MapHit(path, modules[path], via_module=False)
    # 가장 긴 모듈 접두사부터 (langchain_core.pydantic_v1.main → .main 먼저)
    parts = path.split(".")
    for i in range(len(parts) - 1, 0, -1):
        prefix = ".".join(parts[:i])
        if prefix in modules:
            return MapHit(path, modules[prefix], via_module=True)
    return None
