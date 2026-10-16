"""PyPI wheel을 메모리에서 열어 AST로 공개 심볼을 추출한다.

레코드 kind:
    def        모듈 최상위 class/def (deprecated 데코레이터 메타데이터 포함)
    reexport   최상위 `from x import Y` 또는 `Y = 다른 import 이름` 별칭
    lookup     이름에 LOOKUP이 들어간 dict (예: DEPRECATED_LOOKUP, _module_lookup)
    lazy       `__getattr__` / `_import_*` 함수 안의 ImportFrom
    all        `__all__`에만 있고 위에서 출처를 못 찾은 이름

TYPE_CHECKING 블록은 실제 런타임 경로가 아니므로 제외한다.
"""

import ast
import io
import json
import sys
import urllib.request
import warnings
import zipfile

from . import OLD_VERSIONS, TARGET_VERSIONS, VERSION_SETS, SYMBOLS_DIR, symbols_path

PYPI_JSON = "https://pypi.org/pypi/{package}/{version}/json"
DEPRECATED_KEYS = ("since", "removal", "alternative", "alternative_import", "pending", "message")


def open_wheel(package: str, version: str) -> zipfile.ZipFile:
    with urllib.request.urlopen(PYPI_JSON.format(package=package, version=version)) as resp:
        meta = json.load(resp)
    urls = [u["url"] for u in meta["urls"] if u["filename"].endswith(".whl")]
    if not urls:
        raise RuntimeError(f"{package}=={version}: no wheel found")
    with urllib.request.urlopen(urls[0]) as resp:
        return zipfile.ZipFile(io.BytesIO(resp.read()))


def module_name(filename: str) -> str | None:
    if not filename.endswith(".py") or ".dist-info/" in filename:
        return None
    parts = filename[:-3].split("/")
    if parts[-1] == "__init__":
        parts = parts[:-1]
    if any(p in ("tests", "test", "unit_tests", "integration_tests") for p in parts):
        return None
    return ".".join(parts)


def resolve_relative(module: str, is_package: bool, level: int, target: str | None) -> str:
    if level == 0:
        return target or ""
    base = module.split(".")
    if not is_package:
        base = base[:-1]
    if level > 1:
        base = base[: len(base) - (level - 1)]
    return ".".join(base + ([target] if target else []))


def literal(node: ast.AST):
    try:
        return ast.literal_eval(node)
    except (ValueError, SyntaxError, TypeError):
        return ast.unparse(node)


def deprecation_info(decorators: list[ast.expr]) -> dict | None:
    for dec in decorators:
        func = dec.func if isinstance(dec, ast.Call) else dec
        name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
        if name != "deprecated":
            continue
        info = {}
        if isinstance(dec, ast.Call):
            if dec.args:
                info["since"] = literal(dec.args[0])
            for kw in dec.keywords:
                if kw.arg in DEPRECATED_KEYS:
                    info[kw.arg] = literal(kw.value)
        return info
    return None


def is_type_checking(test: ast.expr) -> bool:
    return (isinstance(test, ast.Name) and test.id == "TYPE_CHECKING") or (
        isinstance(test, ast.Attribute) and test.attr == "TYPE_CHECKING"
    )


def runtime_statements(body: list[ast.stmt]):
    """모듈 최상위 문장. if/try 안쪽까지 펼치되 TYPE_CHECKING 블록은 건너뛴다."""
    for stmt in body:
        if isinstance(stmt, ast.If):
            if is_type_checking(stmt.test):
                yield from runtime_statements(stmt.orelse)
            else:
                yield from runtime_statements(stmt.body)
                yield from runtime_statements(stmt.orelse)
        elif isinstance(stmt, ast.Try):
            yield from runtime_statements(stmt.body)
            for handler in stmt.handlers:
                yield from runtime_statements(handler.body)
            yield from runtime_statements(stmt.orelse)
            yield from runtime_statements(stmt.finalbody)
        else:
            yield stmt


def class_methods(node: ast.ClassDef) -> dict:
    """클래스 본문에 정의된 공개 메서드(+ __call__) 이름과, 그중 @deprecated 메서드 정보.

    1.x 에서 메서드가 남아 있는지 확인하고(methods), 구버전 메서드 대응표를 만드는 데(deprecated_methods) 쓴다.
    상속받은 메서드는 정의한 클래스(BaseLLM 등) 쪽에 기록된다.
    """
    methods, deprecated = [], {}
    for item in node.body:
        if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if item.name.startswith("_") and item.name != "__call__":
            continue
        methods.append(item.name)
        dep = deprecation_info(item.decorator_list)
        if dep is not None:
            deprecated[item.name] = dep
    out = {"methods": sorted(set(methods))}
    if deprecated:
        out["deprecated_methods"] = deprecated
    return out


def extract_module(module: str, is_package: bool, source: str) -> list[dict]:
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", SyntaxWarning)  # 대상 소스의 docstring escape 경고
        tree = ast.parse(source)
    records: dict[str, dict] = {}
    imported: dict[str, str] = {}  # 로컬 이름 → 절대 경로
    all_names: list[str] = []
    proxy_modules: list[str] = []  # __getattr__가 getattr(모듈, name)으로 위임하는 대상 모듈

    def add(name: str, kind: str, **extra):
        if name.startswith("_"):
            return
        records.setdefault(name, {"path": f"{module}.{name}", "module": module, "name": name, "kind": kind, **extra})

    def import_from(node: ast.ImportFrom) -> list[tuple[str, str]]:
        src = resolve_relative(module, is_package, node.level, node.module)
        return [(a.asname or a.name, f"{src}.{a.name}") for a in node.names if a.name != "*"]

    for stmt in runtime_statements(tree.body):
        if isinstance(stmt, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            if stmt.name == "__getattr__" or stmt.name.startswith("_import_"):
                # `return getattr(chat_models, name)` 처럼 모듈을 통째로 위임하는 경우
                proxied = {
                    sub.args[0].id
                    for sub in ast.walk(stmt)
                    if isinstance(sub, ast.Call) and isinstance(sub.func, ast.Name)
                    and sub.func.id == "getattr" and sub.args and isinstance(sub.args[0], ast.Name)
                }
                for sub in ast.walk(stmt):
                    if isinstance(sub, ast.ImportFrom):
                        for local, target in import_from(sub):
                            if local in proxied:
                                proxy_modules.append(target)
                            else:
                                add(local, "lazy", target=target)
                continue
            dep = deprecation_info(stmt.decorator_list)
            rec = {"type": "class" if isinstance(stmt, ast.ClassDef) else "function"}
            if dep is not None:
                rec["deprecated"] = dep
            if isinstance(stmt, ast.ClassDef):
                rec.update(class_methods(stmt))
            add(stmt.name, "def", **rec)
        elif isinstance(stmt, ast.ImportFrom):
            for local, target in import_from(stmt):
                imported[local] = target
        elif isinstance(stmt, ast.Assign):
            for tgt in stmt.targets:
                if not isinstance(tgt, ast.Name):
                    continue
                if tgt.id == "__all__" and isinstance(stmt.value, (ast.List, ast.Tuple)):
                    all_names.extend(e.value for e in stmt.value.elts if isinstance(e, ast.Constant))
                elif "lookup" in tgt.id.lower() and isinstance(stmt.value, ast.Dict):
                    deprecated_lookup = "deprecated" in tgt.id.lower()
                    for k, v in zip(stmt.value.keys, stmt.value.values):
                        if not (isinstance(k, ast.Constant) and isinstance(v, ast.Constant)):
                            continue
                        if not (isinstance(k.value, str) and isinstance(v.value, str)):
                            continue
                        target = v.value if v.value.endswith("." + k.value) else f"{v.value}.{k.value}"
                        add(k.value, "lookup", target=target, deprecated_lookup=deprecated_lookup)
                elif isinstance(stmt.value, ast.Name) and stmt.value.id in imported:
                    add(tgt.id, "reexport", target=imported[stmt.value.id])

    # __all__에 있으면 공개 re-export. __all__이 없는 모듈은 langchain 계열 import만 인정
    # (typing·pydantic_v1 같은 내부용 import가 대응표를 오염시키지 않도록)
    for local, target in imported.items():
        internal = (
            not target.startswith(("langchain", "langgraph"))
            or ".pydantic_v1." in target
            or any(p.startswith("_") for p in target.split("."))
        )
        if local in all_names or (not all_names and not internal):
            add(local, "reexport", target=target)
    for name in all_names:
        if len(proxy_modules) == 1:
            add(name, "lazy", target=f"{proxy_modules[0]}.{name}")
        else:
            add(name, "all")
    for name, rec in records.items():
        rec["in_all"] = name in all_names
    return list(records.values())


def extract_package(package: str, version: str) -> list[dict]:
    wheel = open_wheel(package, version)
    out = []
    for filename in sorted(wheel.namelist()):
        module = module_name(filename)
        if module is None or any(p.startswith("_") and p != "__init__" for p in module.split(".")[1:]):
            continue
        try:
            source = wheel.read(filename).decode("utf-8")
            out.extend(extract_module(module, filename.endswith("__init__.py"), source))
        except (SyntaxError, UnicodeDecodeError) as e:
            print(f"  [skip] {filename}: {e}", file=sys.stderr)
    for rec in out:
        rec["package"], rec["version"] = package, version
    return out


def write_jsonl(path, records):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for rec in records:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")


def main():
    SYMBOLS_DIR.mkdir(parents=True, exist_ok=True)
    jobs = [(p, v) for p, vs in OLD_VERSIONS.items() for v in vs] + list(TARGET_VERSIONS.items())
    jobs += [(p, v) for s in VERSION_SETS.values() for p, v in s.items()]
    for package, version in dict.fromkeys(jobs):  # 순서 유지 중복 제거
        records = extract_package(package, version)
        write_jsonl(symbols_path(package, version), records)
        deprecated = sum("deprecated" in r for r in records)
        dep_methods = sum(len(r.get("deprecated_methods", {})) for r in records)
        print(f"{package}=={version}: {len(records)} symbols, {deprecated} deprecated, {dep_methods} deprecated methods")


if __name__ == "__main__":
    main()
