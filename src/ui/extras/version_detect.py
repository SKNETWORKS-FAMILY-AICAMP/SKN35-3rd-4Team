"""[선택 기능 · 4번 영역 아님] 지금 코드가 어느 버전 시기인지 자동 감지.

- 2번 버전별 도구 목록(version_map.py)이 있으면 1.x 까지 포함해 "이 경로들이 모두 있는 버전"을 찾는다.
- 없으면 2번 import 대응표의 seen_in(그 기능이 있던 옛 버전 목록)과 패키지 단서로 짐작한다.
  대응표도 없으면 아래 작은 예시를 쓴다.
"""

import json
from functools import lru_cache
from pathlib import Path

from ..mock import import_paths
from ..versions import ALL, ALL_WITH_NEW

ROOT = Path(__file__).resolve().parents[3]
IMPORT_MAP = ROOT / "data" / "processed" / "import_map.jsonl"

# 2번 대응표가 없을 때 쓰는 예시 (실제 대응표의 seen_in 값을 옮겨 둔 것)
SAMPLE_SEEN = {
    "langchain.LLMBashChain": ["0.0.300"],
    "langchain.agents.create_tool_calling_agent": ["0.1.20", "0.2.17", "0.3.30"],
}
# 새 패키지에서 가져오면 그 패키지가 나온 뒤의 코드
PACKAGE_HINTS = {
    "langchain_core": ("0.0.354", "langchain_core 패키지 사용"),
    "langchain_community": ("0.0.354", "langchain_community 패키지 사용"),
    "langchain_openai": ("0.1.20", "langchain_openai 패키지 사용"),
}


@lru_cache(maxsize=1)
def seen_index() -> dict[str, list[str]] | None:
    if not IMPORT_MAP.exists():
        return None
    idx = {}
    for line in IMPORT_MAP.read_text(encoding="utf-8").splitlines():
        rec = json.loads(line)
        vs = [s.split("==")[1] for s in rec.get("seen_in", []) if s.startswith("langchain==")]
        if vs:
            idx[rec["old"]] = vs
    return idx


def seen_in(path: str) -> list[str] | None:
    idx = seen_index()
    if idx is not None:
        return idx.get(path)
    if path in SAMPLE_SEEN:
        return SAMPLE_SEEN[path]
    from ..mock import SAMPLE_MAP
    return list(ALL) if path in SAMPLE_MAP else None


def _span(vs: list[str]) -> str:
    return vs[0] if len(vs) == 1 else f"{vs[0]}~{vs[-1]}"


def detect(code: str) -> dict:
    """코드가 어느 버전 시기인지 범위로 짐작한다.

    2번 버전별 도구 목록이 있으면 1.x 까지 포함해 "이 경로들이 모두 있는 버전"을 찾고,
    없으면 대응표의 seen_in(옛 버전만)과 패키지 단서로 짐작한다.
    """
    from . import version_map as vm
    paths = [p for _, p in import_paths(code)]
    if paths and vm.available():
        having = vm.versions_having(paths)
        if having:
            clues = []
            for p in paths:
                vs = vm.versions_having([p])
                if len(vs) < len(ALL_WITH_NEW):
                    clues.append(f"`{p.rsplit('.', 1)[1]}` ({_span(vs)}에만 있음)")
            return {"candidates": having, "clues": clues, "source": "2번 버전 목록"}
    candidates = list(ALL)
    clues = []
    for _, path in import_paths(code):
        vs = seen_in(path)
        if not vs:
            continue
        narrowed = [v for v in candidates if v in vs]
        if narrowed and len(vs) < len(ALL):
            clues.append(f"`{path.rsplit('.', 1)[1]}` ({vs[0]}~{vs[-1]}에만 있음)" if len(vs) > 1
                         else f"`{path.rsplit('.', 1)[1]}` ({vs[0]}에만 있음)")
        if narrowed:
            candidates = narrowed
    for line in code.splitlines():
        for pkg, (since, why) in PACKAGE_HINTS.items():
            if line.strip().startswith((f"from {pkg}", f"import {pkg}")):
                narrowed = [v for v in candidates if ALL.index(v) >= ALL.index(since)]
                if narrowed and narrowed != candidates:
                    candidates = narrowed
                    clues.append(why)
    return {"candidates": candidates, "clues": clues, "source": "2번 대응표" if seen_index() is not None else "예시"}


def describe(d: dict) -> str:
    c = d["candidates"]
    span = c[0] if len(c) == 1 else f"{c[0]} ~ {c[-1]}"
    if c == ["1.x"]:
        return "이 코드는 **LangChain 1.x** 코드로 보여요."
    if c in (ALL, ALL_WITH_NEW):
        return (f"이 코드는 **LangChain {span}** 시기 코드로 보여요. 쓰인 기능들이 그 버전들에 모두 있어서 "
                "범위를 더 좁히지는 못했어요. 변환 결과는 같으니 걱정하지 않으셔도 돼요.")
    why = ", ".join(d["clues"])
    return f"이 코드는 **LangChain {span}** 시기 코드로 보여요. (단서: {why})"
