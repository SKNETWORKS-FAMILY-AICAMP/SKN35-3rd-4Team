"""[선택 기능 · 4번 영역 아님] 버전 ↔ 버전 import 대응 (어느 방향이든).

2번이 뽑아 둔 버전별 도구 목록(data/raw/symbols/{패키지}-{버전}.jsonl)을 비교한다.
  - 옛 경로가 목표 버전에도 있으면 → 그대로 (same)
  - 없으면 같은 이름의 도구를 목표 버전에서 찾아 가장 알맞은 경로로 (moved)
  - 목표 버전에 그 이름이 아예 없으면 → 못 바꿈 (unresolved)
1.x 로 갈 때는 mock.py 가 2번 import 대응표(imap-…)를 먼저 쓰고, 여기서는 그 밖의 방향을 맡는다.
도구 목록이 없는 폴더(개인 저장소 · 배포 화면)에서는 available() 이 False 다.
"""

import json
import os
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[3]
SYMBOLS = Path(os.environ.get("MIGRATION_SYMBOLS_DIR") or ROOT / "data" / "raw" / "symbols")

# 화면의 버전 → 그 시기에 함께 쓰던 패키지 목록 (2번 도구 목록 파일 이름)
VERSION_SETS = {
    "0.0.300": ["langchain-0.0.300"],
    "0.0.354": ["langchain-0.0.354", "langchain-core-0.1.53", "langchain-community-0.0.38"],
    "0.1.20": ["langchain-0.1.20", "langchain-core-0.1.53", "langchain-community-0.0.38"],
    "0.2.17": ["langchain-0.2.17", "langchain-core-0.2.43", "langchain-community-0.2.19"],
    "0.3.30": ["langchain-0.3.30", "langchain-core-0.3.86", "langchain-community-0.3.31"],
    "1.x": ["langchain-1.4.5", "langchain-core-1.6.10", "langchain-community-0.4.2", "langchain-classic-1.0.8",
            "langchain-openai-1.7.1", "langchain-text-splitters-1.1.3", "langgraph-1.2.14",
            "langchain-anthropic-1.7.6", "langchain-chroma-1.1.0", "langchain-huggingface-1.2.3",
            "langchain-google-genai-4.4.1", "langchain-ollama-1.1.0"],
}
ORDER = list(VERSION_SETS)                      # 오래된 순
# 목표가 1.x 일 때 고르는 순서 (분리된 전용 패키지 → core → 분할기 → community → langchain → classic)
PREFER_NEW = ["langchain_openai", "langchain_anthropic", "langchain_huggingface", "langchain_google_genai",
              "langchain_ollama", "langchain_chroma", "langchain_core", "langchain_text_splitters", "langgraph",
              "langchain_community", "langchain", "langchain_classic"]
# 목표가 0.x 일 때 (그 시기 사용자가 주로 쓰던 langchain.* → core → community)
PREFER_OLD = ["langchain", "langchain_core", "langchain_community"]
# pydantic 의 도구: 0.3 부터는 pydantic 에서 직접, 그 전에는 LangChain 의 pydantic_v1 호환 자리
PYDANTIC_NAMES = {"BaseModel", "Field", "validator", "root_validator", "SecretStr", "ConfigDict", "model_validator"}


def available() -> bool:
    return SYMBOLS.exists() and all((SYMBOLS / f"{f}.jsonl").exists() for fs in VERSION_SETS.values() for f in fs[:1])


@lru_cache(maxsize=None)
def _index(version: str) -> tuple[frozenset[str], dict[str, tuple[tuple[str, bool], ...]]]:
    """(경로 집합, 이름 → (경로, 공식 공개 여부)들)."""
    paths, by_name = set(), {}
    for stem in VERSION_SETS[version]:
        f = SYMBOLS / f"{stem}.jsonl"
        if not f.exists():
            continue
        for line in f.read_text(encoding="utf-8").splitlines():
            rec = json.loads(line)
            if rec["name"].startswith("_"):
                continue
            paths.add(rec["path"])
            by_name.setdefault(rec["name"], []).append((rec["path"], bool(rec.get("in_all"))))
    return frozenset(paths), {k: tuple(v) for k, v in by_name.items()}


def _rank(cand: tuple[str, bool], prefer: list[str]) -> tuple[int, int, int, int, int]:
    """공식 공개(__all__) 경로 우선 → 선호 패키지 → 옛 호환 자리(pydantic_v1 · schema) 뒤로 → 짧은 경로."""
    path, public = cand
    top = path.split(".")[0]
    compat = 1 if ".pydantic_v1" in path or ".schema" in path else 0
    shortcut = 1 if top == "langchain" and path.count(".") == 1 else 0     # langchain.X 최상위 바로가기는 뒤로
    return (0 if public else 1, prefer.index(top) if top in prefer else len(prefer), compat, shortcut,
            path.count("."))


def has(path: str, version: str) -> bool:
    return path in _index(version)[0]


def translate(path: str, target: str) -> dict:
    """옛 경로 하나를 목표 버전 경로로. kind: same / moved / classic_fallback / unresolved."""
    paths, by_name = _index(target)
    name = path.rsplit(".", 1)[1]
    if path in paths:
        return {"new": path, "kind": "same"}
    if name in PYDANTIC_NAMES and (".pydantic_v1" in path or path.startswith("pydantic")):
        if ORDER.index(target) >= ORDER.index("0.3.30"):
            return {"new": f"pydantic.{name}", "kind": "moved"}
        # 0.2 이전에는 LangChain 의 pydantic_v1 호환 자리 (도구 목록에 안 잡히는 지연 로딩이라 직접 지정)
        home = "langchain.pydantic_v1" if target in ("0.0.300", "0.0.354") else "langchain_core.pydantic_v1"
        return {"new": f"{home}.{name}", "kind": "moved"}
    candidates = by_name.get(name, ())
    if not candidates:
        return {"new": None, "kind": "unresolved"}
    prefer = PREFER_NEW if target == "1.x" else PREFER_OLD
    best = min(candidates, key=lambda c: _rank(c, prefer))[0]
    return {"new": best, "kind": "classic_fallback" if best.startswith("langchain_classic") else "moved"}


def versions_having(paths: list[str]) -> list[str]:
    """이 경로들이 모두 있는 버전 목록 (오래된 순)."""
    return [v for v in ORDER if all(has(p, v) for p in paths)]
