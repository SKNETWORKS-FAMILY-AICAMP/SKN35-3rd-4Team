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


# ---------------------------------------------------------------- 메서드 대응표

METHOD_CALL = re.compile(r"\.([A-Za-z_]\w*)\s*\(")
# 객체를 직접 호출하는 구버전 패턴 (llm("..."), chat([...]), chain({...})) — 변수 이름으로 추정
DIRECT_CALL = re.compile(
    r"(?<![\w.])(llm|chat|chat_model|model|chain|qa|qa_chain|llm_chain|agent|agent_executor|tool)\s*\(")
# 질의에 이런 단서가 있으면 해당 클래스 계열의 메서드를 우선
CLASS_HINTS = {
    "BaseChatModel": re.compile(r"\bChat[A-Z]\w*|chat_model|\bchat\b"),
    "BaseLLM": re.compile(r"\b(OpenAI|HuggingFaceHub|Ollama|LlamaCpp|Anthropic)\s*\(|\bllm\b"),
    "BaseRetriever": re.compile(r"retriever|as_retriever"),
    "Chain": re.compile(r"Chain\b|\bchain\b"),
    "BaseTool": re.compile(r"\btool\b|Tool\b"),
}
MAX_METHOD_HITS_PER_NAME = 3


@lru_cache(maxsize=1)
def _load_methods() -> dict[str, list[dict]]:
    from . import METHOD_MAP_PATH

    by_name: dict[str, list[dict]] = {}
    with METHOD_MAP_PATH.open(encoding="utf-8") as f:
        for line in f:
            rec = json.loads(line)
            by_name.setdefault(rec["method"], []).append(rec)
    return by_name


def find_method_calls(code: str) -> list[str]:
    """질의 코드에서 메서드 대응표에 있는 메서드 호출 이름을 찾는다 (직접 호출은 __call__)."""
    known = _load_methods()
    names = [m for m in METHOD_CALL.findall(code) if m in known]
    if DIRECT_CALL.search(code) and "__call__" in known:
        names.append("__call__")
    return list(dict.fromkeys(names))


def lookup_methods(code: str) -> list[dict]:
    """메서드 호출 → 대응표 레코드. 같은 메서드 이름이 여러 클래스에 있으면 질의 단서로 순위를 매긴다."""
    known = _load_methods()
    hits = []
    for name in find_method_calls(code):
        ranked = []
        for rec in known[name]:
            score = 0
            if any(re.search(rf"\b{re.escape(c)}\b", code) for c in rec["classes"]):
                score += 2  # 클래스 이름이 질의에 직접 나옴 (ConversationChain 등)
            hint = CLASS_HINTS.get(rec["class"])
            if hint and hint.search(code):
                score += 1
            if rec["status_1x"] == "removed":
                score += 0.5  # 1.x 에서 실제로 오류가 나는 쪽을 먼저
            ranked.append((score, rec))
        ranked.sort(key=lambda x: -x[0])
        best = ranked[0][0]
        # 질의 단서가 가장 잘 맞는 후보만 (ConversationChain.predict 가 맞으면 BaseLLM.predict 는 뺀다)
        hits.extend(rec for score, rec in ranked[:MAX_METHOD_HITS_PER_NAME] if score == best)
    return hits
