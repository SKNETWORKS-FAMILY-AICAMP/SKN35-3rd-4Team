"""심볼 목록 + CLI 매핑을 병합해 구버전 경로 → 1.x 경로 대응표를 만든다.

해석 순서 (구버전 경로 P에서 출발해 간선을 따라감):
    1. langchain-cli 매핑 (심볼 단위, pydantic_v1 같은 모듈 단위)
    2. @deprecated(alternative_import=...)  (1.x 대상 → 구버전 순)
    3. re-export / lookup / lazy import 의 원래 정의 위치 (최신 구버전부터)
1.x 대상에 존재하고 deprecated가 아닌 경로에 닿으면 kind=native.
못 닿으면 langchain.X → langchain_classic.X 가 있을 때 kind=classic_fallback.
그것도 없으면 kind=unresolved로 두고 alternative 텍스트(예: "prompt | llm")를 남긴다.
P 자체가 1.x에 그대로 있으면 대응표에서 제외한다.

마지막에 1.x 패키지를 설치한 임시 환경(uv --isolated)에서 new 경로를 실제로 import 해 본다.

메서드 대응표(method_map.jsonl)도 함께 만든다: 구버전 클래스의 @deprecated 메서드(chain.run 등)를
1.x 클래스와 대조해 removed / deprecated / exists 를 판정하고, manual_method_map 의 보강분을 더한다.
"""

import hashlib
import json
import re
import subprocess
import sys
import tempfile
from collections import Counter, defaultdict

from . import (
    CLI_MAPPINGS_PATH, IMPORT_MAP_PATH, METHOD_MAP_PATH, OLD_VERSIONS, PYTHON_VERSION, TARGET_VERSIONS, symbols_path,
)
from .extract_symbols import write_jsonl
from .manual_method_map import MANUAL_METHODS, METHOD_NOTES

TARGET_MODULES = {p.replace("-", "_") for p in TARGET_VERSIONS}
MAX_DEPTH = 12

# pydantic_v1 shim은 `from pydantic.v1 import *` 라 심볼을 정적으로 알 수 없다.
# 모듈 단위 매핑과 함께 자주 쓰이는 이름만 심볼 단위로 펼쳐 둔다.
PYDANTIC_V1_NAMES = [
    "BaseModel", "Field", "SecretStr", "root_validator", "validator", "Extra",
    "PrivateAttr", "ValidationError", "create_model", "conint", "constr", "StrictStr",
]

IMPORT_CHECK = r"""
import importlib, json, sys, warnings
warnings.simplefilter("ignore")
results = {}
for path, granularity in json.load(open(sys.argv[1])):
    try:
        if granularity == "module":
            importlib.import_module(path)
        else:
            module, _, name = path.rpartition(".")
            getattr(importlib.import_module(module), name)
        results[path] = None
    except BaseException as e:  # SystemExit 등까지 기록
        results[path] = f"{type(e).__name__}: {e}"[:300]
json.dump(results, open(sys.argv[2], "w"))
"""


def load_jsonl(path):
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def version_key(version: str):
    return tuple(int(x) for x in version.split("."))


class SymbolTable:
    """경로 → 레코드. 같은 경로가 여러 버전에 있으면 최신 버전이 앞에 오도록 보관."""

    def __init__(self):
        self.by_path: dict[str, list[dict]] = defaultdict(list)

    def add(self, records):
        for rec in records:
            self.by_path[rec["path"]].append(rec)

    def finalize(self):
        for recs in self.by_path.values():
            recs.sort(key=lambda r: version_key(r["version"]), reverse=True)

    def __contains__(self, path):
        return path in self.by_path

    def deprecation(self, path: str) -> dict | None:
        """re-export를 따라가 정의부의 @deprecated 정보를 찾는다 (같은 버전 안에서)."""
        seen = set()
        for _ in range(MAX_DEPTH):
            if path in seen or path not in self.by_path:
                return None
            seen.add(path)
            rec = self.by_path[path][0]
            if "deprecated" in rec:
                return rec["deprecated"]
            if rec.get("deprecated_lookup"):
                return {"lookup": True}
            if "target" not in rec:
                return None
            path = rec["target"]
        return None

    def definition(self, path: str) -> dict | None:
        """re-export 를 따라가 같은 테이블 안의 정의(def) 레코드를 찾는다."""
        seen = set()
        while path in self.by_path and path not in seen:
            seen.add(path)
            rec = self.by_path[path][0]
            if rec["kind"] == "def":
                return rec
            if "target" not in rec:
                return None
            path = rec["target"]
        return None

    def origins(self, path: str) -> list[str]:
        return list(dict.fromkeys(r["target"] for r in self.by_path.get(path, []) if "target" in r))


def load_cli():
    symbol, module = defaultdict(list), {}
    for rec in load_jsonl(CLI_MAPPINGS_PATH):
        if rec["granularity"] == "module":
            module[rec["old"]] = rec["new"]
        else:
            symbol[rec["old"]].append(rec["new"])
    return symbol, module


class Resolver:
    def __init__(self, old: SymbolTable, target: SymbolTable, cli_symbol, cli_module):
        self.old, self.target = old, target
        self.cli_symbol, self.cli_module = cli_symbol, cli_module

    def is_external(self, path: str) -> bool:
        """대상 1.x 패키지 밖 (pydantic, langchain_pinecone 등): 정적 확인 대신 import 검증에 맡긴다."""
        top = path.split(".")[0]
        return top not in TARGET_MODULES and top not in {"langchain_community", "langchain_core", "langchain"}

    def edges(self, path: str):
        for new in self.cli_symbol.get(path, []):
            yield new, "cli"
        module, _, name = path.rpartition(".")
        if module in self.cli_module:
            yield f"{self.cli_module[module]}.{name}", "cli"
        for table, label in ((self.target, "deprecated_target"), (self.old, "deprecated")):
            dep = table.deprecation(path)
            if dep and isinstance(dep.get("alternative_import"), str):
                yield dep["alternative_import"], label
        for origin in self.old.origins(path):
            yield origin, "origin"

    def resolve(self, start: str) -> dict:
        """DFS. 첫 번째로 닿는 '1.x에 존재 + 비-deprecated' 경로를 채택."""
        best_deprecated = None  # 1.x에 있지만 deprecated인 경로 (최후 수단)
        visited: list[str] = []
        stack = [(start, [start], [])]
        while stack:
            path, chain, sources = stack.pop()
            if path in visited or len(chain) > MAX_DEPTH:
                continue
            visited.append(path)
            if path != start:
                if self.is_external(path):
                    return {"new": path, "chain": chain, "sources": sources}
                if path in self.target:
                    if self.target.deprecation(path) is None:
                        return {"new": path, "chain": chain, "sources": sources}
                    best_deprecated = best_deprecated or {"new": path, "chain": chain, "sources": sources}
            # 먼저 시도할 간선이 스택 위에 오도록 역순으로 push
            for new, label in reversed(list(self.edges(path))):
                stack.append((new, chain + [new], sources + [label]))

        if best_deprecated:
            return best_deprecated
        for path in visited:
            if path.startswith("langchain."):
                classic = "langchain_classic." + path[len("langchain."):]
                if classic in self.target:
                    return {"new": classic, "chain": visited[: visited.index(path) + 1] + [classic],
                            "sources": ["classic"]}
        return {"new": None, "chain": visited, "sources": []}

    def deprecation_along(self, chain: list[str]) -> dict:
        # 1.x 쪽 정보 우선, 체인 안에서는 new에 가까운 경로 우선
        for table in (self.target, self.old):
            for path in reversed(chain):
                dep = table.deprecation(path)
                if dep and not dep.get("lookup"):
                    return dep
        return {}


def record_id(old: str) -> str:
    return "imap-" + hashlib.sha1(old.encode()).hexdigest()[:10]


def check_imports(records: list[dict]) -> dict[str, str | None]:
    targets = sorted({(r["new"], r["granularity"]) for r in records if r["new"]})
    packages = [f"{p}=={v}" for p, v in TARGET_VERSIONS.items()] + ["pydantic"]
    with tempfile.TemporaryDirectory() as tmp:
        inp, out = f"{tmp}/in.json", f"{tmp}/out.json"
        with open(inp, "w") as f:
            json.dump(targets, f)
        cmd = ["uv", "run", "--isolated", "--no-project", "--python", PYTHON_VERSION]
        for pkg in packages:
            cmd += ["--with", pkg]
        cmd += ["python", "-c", IMPORT_CHECK, inp, out]
        print(f"import 검증: {len(targets)}개 경로 ({' '.join(packages)})")
        subprocess.run(cmd, check=True, cwd=tmp)
        with open(out) as f:
            return json.load(f)


def load_resolver() -> "Resolver":
    old, target = SymbolTable(), SymbolTable()
    for package, versions in OLD_VERSIONS.items():
        for version in versions:
            old.add(load_jsonl(symbols_path(package, version)))
    for package, version in TARGET_VERSIONS.items():
        target.add(load_jsonl(symbols_path(package, version)))
    old.finalize()
    target.finalize()
    cli_symbol, cli_module = load_cli()
    return Resolver(old, target, cli_symbol, cli_module)


def build(resolver: "Resolver", skip_import_check: bool = False) -> list[dict]:
    old, target = resolver.old, resolver.target
    cli_symbol, cli_module = resolver.cli_symbol, resolver.cli_module

    shim_paths = {f"{m}.{n}" for m in cli_module if m.endswith(".pydantic_v1") for n in PYDANTIC_V1_NAMES}
    starts = set(old.by_path) | set(cli_symbol) | shim_paths
    records = []
    for path in sorted(starts):
        if path in target and target.deprecation(path) is None:
            continue  # 1.x에 그대로 존재
        res = resolver.resolve(path)
        new = res["new"]
        if new == path:
            continue
        dep = resolver.deprecation_along(res["chain"])
        if new is None:
            kind = "unresolved"
        elif new.startswith("langchain_classic."):
            kind = "classic_fallback"
        else:
            kind = "native"
        records.append({
            "id": record_id(path),
            "old": path,
            "new": new,
            "kind": kind,
            "granularity": "symbol",
            "chain": res["chain"],
            "sources": sorted(set(res["sources"])),
            "since": dep.get("since"),
            "removal": dep.get("removal"),
            "alternative": dep.get("alternative"),
            "seen_in": sorted({f"{r['package']}=={r['version']}" for r in old.by_path.get(path, [])},
                              key=lambda s: (s.split("==")[0], version_key(s.split("==")[1]))),
        })

    for old_module, new_module in sorted(cli_module.items()):
        records.append({
            "id": record_id(old_module), "old": old_module, "new": new_module, "kind": "native",
            "granularity": "module", "chain": [old_module, new_module], "sources": ["cli"],
            "since": None, "removal": None, "alternative": None, "seen_in": [],
        })

    results = {} if skip_import_check else check_imports(records)
    for rec in records:
        if skip_import_check or rec["new"] is None:
            rec["import_ok"], rec["import_error"], rec["import_status"] = None, None, None
            continue
        err = results.get(rec["new"])
        rec["import_ok"], rec["import_error"] = err is None, err
        rec["import_status"] = import_status(rec["new"], err)
    return records


def import_status(new: str, err: str | None) -> str:
    """ok / missing_package (검증 환경에 없는 파트너 패키지) / missing_dependency / error"""
    if err is None:
        return "ok"
    missing = re.match(r"ModuleNotFoundError: No module named '([^'.]+)", err)
    if missing:
        return "missing_package" if missing.group(1) == new.split(".")[0] else "missing_dependency"
    return "error"


def method_id(key: str) -> str:
    return "mmap-" + hashlib.sha1(key.encode()).hexdigest()[:10]


def call_form(method: str) -> str:
    return "obj(...)" if method == "__call__" else f".{method}(...)"


def build_method_map(resolver: "Resolver") -> list[dict]:
    """구버전 클래스의 @deprecated 메서드 → 1.x 상태(removed / deprecated / exists) + 직접 보강분."""
    old, target = resolver.old, resolver.target
    records = []
    for class_path, versions in sorted(old.by_path.items()):
        latest = versions[0]  # 최신 구버전 레코드
        deprecated_methods: dict[str, dict] = {}
        for rec in reversed(versions):  # 오래된 버전부터 덮어써서 최신 정보가 남게
            deprecated_methods.update(rec.get("deprecated_methods", {}))
        if latest.get("type") != "class" or not deprecated_methods:
            continue

        if class_path in target:
            class_new = class_path
        else:
            class_new = resolver.resolve(class_path)["new"]
        definition = target.definition(class_new) if class_new else None

        for method, dep in sorted(deprecated_methods.items()):
            if definition is None:
                status = "removed"  # 클래스 자체가 1.x 에 없음
            elif method in definition.get("deprecated_methods", {}):
                status = "deprecated"
            elif method in definition.get("methods", []):
                status = "exists"
            else:
                status = "removed"
            extra = METHOD_NOTES.get(method, {})
            records.append({
                "id": method_id(f"{class_path}.{method}"),
                "class": latest["name"],
                "classes": [latest["name"]],
                "class_path": class_path,
                "class_new": class_new,
                "method": method,
                "call": call_form(method),
                "alternative": dep.get("alternative"),
                "since": dep.get("since"),
                "removal": dep.get("removal"),
                "status_1x": status,
                "note": extra.get("note"),
                "doc_refs": extra.get("doc_refs", []),
                "source": "deprecated",
                "seen_in": sorted({f"{r['package']}=={r['version']}" for r in versions
                                   if method in r.get("deprecated_methods", {})}),
            })

    for item in MANUAL_METHODS:
        records.append({
            "id": method_id(f"manual:{item['class']}.{item['method']}"),
            "class": item["class"],
            "classes": item["classes"],
            "class_path": None,
            "class_new": None,
            "method": item["method"],
            "call": call_form(item["method"]),
            "alternative": item["alternative"],
            "since": None,
            "removal": None,
            "status_1x": "deprecated",
            "note": item["note"],
            "doc_refs": item["doc_refs"],
            "source": "manual",
            "seen_in": [],
        })
    return records


def main():
    resolver = load_resolver()
    records = build(resolver, skip_import_check="--skip-import-check" in sys.argv)
    write_jsonl(IMPORT_MAP_PATH, records)
    print(f"{IMPORT_MAP_PATH.relative_to(IMPORT_MAP_PATH.parents[2])}: {len(records)} records")
    print("  kind:", dict(Counter(r["kind"] for r in records)))
    print("  import_status:", dict(Counter(str(r["import_status"]) for r in records)))

    methods = build_method_map(resolver)
    write_jsonl(METHOD_MAP_PATH, methods)
    print(f"{METHOD_MAP_PATH.relative_to(METHOD_MAP_PATH.parents[2])}: {len(methods)} records")
    print("  status_1x:", dict(Counter(r["status_1x"] for r in methods)))
    print("  source:", dict(Counter(r["source"] for r in methods)))


if __name__ == "__main__":
    main()
