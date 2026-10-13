"""버전 정보: 시작 화면의 마인드맵 요약, 코드의 옛 버전 자동 감지.

- 요약 숫자: version_summary.json (2번 import 대응표를 버전 · 영역별로 센 것)
- 자동 감지: 대응표의 seen_in(그 기능이 있던 옛 버전 목록)을 코드의 import 마다 겹쳐 본다.
  팀 저장소에 data/processed/import_map.jsonl 이 있으면 그것을, 없으면 아래 작은 예시를 쓴다.
"""

import json
from functools import lru_cache
from pathlib import Path

from .mock import import_paths

ROOT = Path(__file__).resolve().parents[2]
SUMMARY = json.loads((Path(__file__).with_name("version_summary.json")).read_text(encoding="utf-8"))
IMPORT_MAP = ROOT / "data" / "processed" / "import_map.jsonl"
ALL = [v["version"] for v in SUMMARY["versions"]]          # 옛 버전, 오래된 순

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
    from .mock import SAMPLE_MAP
    return list(ALL) if path in SAMPLE_MAP else None


def detect(code: str) -> dict:
    """코드가 어느 옛 버전 시기인지 범위로 짐작한다."""
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
    if c == ALL:
        return (f"이 코드는 **LangChain {span}** 시기 코드로 보여요. 쓰인 기능들이 옛 버전 전체에 있어서 "
                "범위를 더 좁히지는 못했어요. 변환 결과는 같으니 걱정하지 않으셔도 돼요.")
    why = ", ".join(d["clues"])
    return f"이 코드는 **LangChain {span}** 시기 코드로 보여요. (단서: {why})"
