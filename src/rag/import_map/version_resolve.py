"""목표 버전 기준 import 경로 판정 (업그레이드·다운그레이드 공통).

사용자가 말한 버전(없으면 최신)을 VERSION_SETS 대표 버전으로 맞추고, 경로 하나를
그 버전의 심볼 목록과 import_map 체인으로 판정한다. 원래 코드의 버전은 쓰지 않는다.

    resolve("langchain.chat_models.ChatOpenAI")            # 최신 1.4.5 기준
    resolve("langchain_core.prompts.PromptTemplate", normalize_version("0.0.300"))

판정 순서:
    1. 목표 버전에 있고 deprecated가 아니면 keep
    2. import_map 체인을 양방향 그래프로 보고 가까운 순으로 탐색해 목표 버전에 있는 경로를 찾으면 moved
       (후보 순위: 비-deprecated > 목표 세트 밖 > deprecated, 그 안에서 거리 → 같은 이름 → 모듈 깊이 3에 가까운 것)
    3. 1에서 deprecated였는데 갈 곳이 없으면 그대로 keep (deprecated 정보 포함)
    4. 경로의 최상위 패키지를 목표 세트가 모르면 unknown, 알면 not_available
목표 세트 밖 패키지(langchain_aws, pydantic 등)에 닿은 경로는 존재를 확인할 수 없어 verified=False.
경로 자체가 목표 세트 밖 패키지면 2의 후보가 deprecated일 때 옮기지 않고 keep(verified=False).
"""

import re
from collections import defaultdict, deque
from dataclasses import dataclass
from functools import lru_cache

from . import IMPORT_MAP_PATH, LATEST_VERSION, TARGET_VERSIONS, VERSION_SETS, symbols_path
from .build_import_map import SymbolTable, load_jsonl, version_key

MAX_DISTANCE = 6
CORE_TOPS = {"langchain", "langchain_core", "langchain_community"}
ONLY_1X_TOPS = {"langchain_classic"}  # 1.0 이전에는 없던 패키지 — 0.x 목표에서는 후보가 될 수 없다
VERSION_TEXT = re.compile(r"(\d+)\.(\d+)(?:\.(\d+))?")


@dataclass(frozen=True)
class Resolution:
    path: str                       # 사용자 코드의 경로
    target: str                     # 대표 버전 (예: "0.2.17")
    status: str                     # keep | moved | not_available | unknown
    new: str | None = None          # keep이면 path, moved면 바뀐 경로
    chain: tuple[str, ...] = ()     # path → … → new
    evidence_ids: tuple[str, ...] = ()  # 지나온 간선의 import_map 레코드 id
    deprecated: dict | None = None  # new가 목표 버전에서 deprecated일 때 그 정보
    verified: bool = True           # new가 목표 세트 심볼 목록에서 확인됐는지
    alternative: str | None = None  # not_available일 때 import_map의 대안 설명


def normalize_version(text: str | None) -> str:
    """사용자가 말한 버전 → VERSION_SETS 대표 버전. 없으면 최신."""
    if not text or text.strip().lower() in ("latest", "newest"):
        return LATEST_VERSION
    m = VERSION_TEXT.search(text)
    if not m:
        raise ValueError(f"cannot parse version: {text!r}")
    major, minor, patch = int(m[1]), int(m[2]), m[3]
    same_minor = sorted((v for v in VERSION_SETS if version_key(v)[:2] == (major, minor)), key=version_key)
    if not same_minor:
        raise ValueError(f"unsupported version: {text!r} (supported: {', '.join(VERSION_SETS)})")
    if patch is None or len(same_minor) == 1:
        return same_minor[-1]
    # 0.0.x처럼 대표가 여럿이면 패치 번호가 가장 가까운 것
    return min(same_minor, key=lambda v: abs(version_key(v)[2] - int(patch)))


@lru_cache(maxsize=None)
def _target_table(target: str) -> tuple[SymbolTable, frozenset[str], frozenset[str]]:
    """대표 버전의 심볼 테이블, 모듈 집합, 최상위 패키지 집합."""
    packages = dict(VERSION_SETS[target])
    if version_key(target)[0] >= 1:
        # 파트너 패키지(openai 등)는 langchain 버전과 묶이지 않아 1.x 세트 모두에 최신을 근사로 붙인다
        for package, version in TARGET_VERSIONS.items():
            packages.setdefault(package, version)
    table = SymbolTable()
    modules = set()
    for package, version in packages.items():
        records = load_jsonl(symbols_path(package, version))
        table.add(records)
        modules.update(r["module"] for r in records)
    table.finalize()
    tops = frozenset(p.replace("-", "_") for p in packages)
    return table, frozenset(modules), tops


@lru_cache(maxsize=1)
def _graph() -> tuple[dict[str, dict[str, str]], dict[str, dict], dict[str, dict]]:
    """import_map 체인 → 무방향 그래프 {경로: {이웃: 레코드 id}}, old별 레코드, 모듈 단위 레코드."""
    graph: dict[str, dict[str, str]] = defaultdict(dict)
    by_old, modules = {}, {}
    for rec in load_jsonl(IMPORT_MAP_PATH):
        (modules if rec["granularity"] == "module" else by_old)[rec["old"]] = rec
        if not rec["new"]:
            continue  # unresolved의 chain은 방문 목록이라 간선이 아니다
        for a, b in zip(rec["chain"], rec["chain"][1:]):
            graph[a].setdefault(b, rec["id"])
            graph[b].setdefault(a, rec["id"])
    return graph, by_old, modules


def _exists(path: str, target: str) -> bool:
    table, modules, _ = _target_table(target)
    return path in table or path in modules


def _is_external(path: str, target: str) -> bool:
    top = path.split(".")[0]
    if top in ONLY_1X_TOPS and version_key(target)[0] < 1:
        return False
    return top not in _target_table(target)[2] and top not in CORE_TOPS


def _rank(path: str, start: str, distance: int, target: str) -> tuple:
    table = _target_table(target)[0]
    deprecated = table.deprecation(path) is not None
    # __all__에 있는 공개 경로 우선 (모듈 안에서 import만 해 둔 별칭은 뒤로)
    public = path in table and any(r.get("in_all") for r in table.by_path[path])
    same_name = path.rsplit(".", 1)[-1] == start.rsplit(".", 1)[-1]
    return (deprecated, not public, distance, not same_name, abs(path.count(".") - 2), path)


def _search(start: str, target: str):
    """BFS. 목표 버전에 있는 후보 중 최고 순위, 없으면 목표 세트 밖 경로 중 가장 가까운 것."""
    graph = _graph()[0]
    parent: dict[str, tuple[str, str] | None] = {start: None}
    queue = deque([(start, 0)])
    found, external = [], []
    while queue:
        path, distance = queue.popleft()
        if path != start:
            if _exists(path, target):
                found.append((_rank(path, start, distance, target), path))
            elif _is_external(path, target):
                external.append((distance, path))
        if distance >= MAX_DISTANCE:
            continue
        for neighbor, rec_id in graph.get(path, {}).items():
            if neighbor not in parent:
                parent[neighbor] = (path, rec_id)
                queue.append((neighbor, distance + 1))
    # 대응표 생성 규칙과 같게: 비-deprecated > 목표 세트 밖(확인 불가) > deprecated
    live = [c for c in found if not c[0][0]]
    if live:
        best, verified = min(live)[1], True
    elif external:
        best, verified = min(external)[1], False
    elif found:
        best, verified = min(found)[1], True
    else:
        return None
    chain, ids, node = [best], [], best
    while parent[node] is not None:
        node, rec_id = parent[node]
        chain.append(node)
        ids.append(rec_id)
    return tuple(reversed(chain)), tuple(dict.fromkeys(reversed(ids))), verified


def resolve(path: str, target: str = LATEST_VERSION) -> Resolution:
    if target not in VERSION_SETS:
        target = normalize_version(target)
    table = _target_table(target)[0]
    deprecation = table.deprecation(path) if _exists(path, target) else None
    if _exists(path, target) and deprecation is None:
        return Resolution(path, target, "keep", new=path, chain=(path,))

    found = _search(path, target)
    if found is None:
        # 모듈 단위 매핑 (langchain_core.pydantic_v1.BaseModel → pydantic.BaseModel)
        _, _, modules = _graph()
        parts = path.split(".")
        for i in range(len(parts) - 1, 0, -1):
            prefix = ".".join(parts[:i])
            rec = modules.get(prefix)
            if rec and rec["new"] and not _exists(prefix, target):
                new = rec["new"] + path[len(prefix):]
                return Resolution(path, target, "moved", new=new, chain=(path, new), evidence_ids=(rec["id"],),
                                  verified=_exists(new, target))
    if found is not None:
        chain, ids, verified = found
        new = chain[-1]
        new_deprecation = table.deprecation(new) if verified else None
        # 목표 세트 밖 패키지(0.x 목표의 langchain_openai 등)는 그 버전에도 쓸 수 있을 수 있어
        # deprecated 경로로는 옮기지 않는다 (langserve.pydantic_v1 → pydantic 같은 밖→밖 이동은 그대로)
        if _is_external(path, target) and new_deprecation is not None:
            return Resolution(path, target, "keep", new=path, chain=(path,), verified=False)
        # deprecated → deprecated는 정의가 있는 패키지 쪽으로 갈 때만 (community 별칭 → classic 정의는 허용,
        # 같은 패키지 안 별칭끼리나 core 정의 → 다른 패키지 별칭은 얻는 게 없다)
        if deprecation is not None and new_deprecation is not None:
            definition = table.definition(path)
            home = definition["path"].split(".")[0] if definition else None
            if not (home and new.split(".")[0] == home != path.split(".")[0]):
                return Resolution(path, target, "keep", new=path, chain=(path,), deprecated=deprecation)
        return Resolution(path, target, "moved", new=new, chain=chain, evidence_ids=ids,
                          deprecated=new_deprecation, verified=verified)
    if deprecation is not None:
        return Resolution(path, target, "keep", new=path, chain=(path,), deprecated=deprecation)

    rec = _graph()[1].get(path)
    alternative = rec["alternative"] if rec else None
    if _is_external(path, target):
        return Resolution(path, target, "unknown", alternative=alternative, verified=False)
    return Resolution(path, target, "not_available", alternative=alternative,
                      evidence_ids=(rec["id"],) if rec else ())
