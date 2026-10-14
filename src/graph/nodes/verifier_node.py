"""verifier 노드: rewriter 결과 검사

검사 항목 (error는 재시도 사유 / warning은 보고서용)
    1. 문법          new_code가 파싱되는가                                    syntax_error
    2. 근거 ID       changes의 근거 ID가 '이번 프롬프트에 보여준 근거'에 있는가   missing_evidence / evidence_not_shown / unknown_evidence_id
    3. 변경 기록     changes의 old가 원본 그 줄과 같은가, new가 결과 코드에 있는가  old_line_mismatch / change_not_applied
                     기록 없이 바뀐 줄이 있는가 (근거 없는 변경 = 환각)             unrecorded_change
    4. 구버전 import 대응표에 있는 구 경로가 남았는가                              legacy_import_remaining  (경고: no_1x_path)
    5. import 존재   새 import 경로가 1.x에 실제로 있는가, 근거가 있는가            import_failed / ungrounded_import
                                                                               (경고: install_required, import_unverified, import_not_in_evidence)
    6. 구버전 메서드 대응표의 메서드 호출이 남았는가 (이름만으로 찾으므로 경고만)    legacy_method_remaining
    7. 안 쓰는 import 원래 쓰던 이름의 import가 변환 후 안 쓰이는가               unused_import  (원래부터 안 쓰던 것은 경고)
    8. 반환값 보존   문자열을 돌려주던 호출(.run/.predict)을 LCEL로 바꾸면서      return_type_changed
                     출력 파서도 .content도 없이 끝냈는가

import 존재 확인 순서 (5번)
    a. 그 경로를 준 import_map 근거가 있으면 대응표 빌드 때 실제로 import 해 본 결과(import_status)를 쓴다
    b. 없으면 1.x 심볼 덤프(data/raw/symbols/{패키지}-{1.x 버전}.jsonl)로 정적 확인
    c. VERIFIER_SANDBOX=1이면 b 대신 uv 격리 환경에 1.x 패키지를 설치해 실제로 import 한다
       (프로젝트 venv에는 langchain-classic 등이 없어서 거기서 import 하면 정상 경로도 실패한다)

재시도 연결
    - exclude_ids에는 '근거 자체가 틀린' 경우(import_failed + 근거 ID 있음)만 넣는다.
      ID를 잘못 단 것, 문법 오류 등은 근거 탓이 아니므로 넣지 않는다 (통과한 근거가 제외되면 재시도 루프가 깨진다)
    - attempt를 1 올린다. 다음 경로는 route_after_verify()가 정한다.

state.py
    evidences, shown_evidence_ids, changes, unresolved, old_code, new_code, rewrite_failed를 읽고
    verify_result, attempt, exclude_ids(merge_ids reducer: 합집합 누적)를 쓴다

단독 실행 (프로젝트 루트에서, OpenAI 키 불필요):
    uv run python -m src.graph.nodes.verifier_node
    VERIFIER_SANDBOX=1 uv run python -m src.graph.nodes.verifier_node     # 실제 import 검사
"""

import ast
import difflib
import json
import os
import re
import subprocess
import tempfile
from functools import lru_cache

from src.graph.state import MigrationState
from src.rag.import_map import PYTHON_VERSION, TARGET_VERSIONS, symbols_path
from src.rag.retrieval.import_lookup import lookup, lookup_methods, parse_import_paths

MAX_ATTEMPTS = int(os.getenv("VERIFIER_MAX_ATTEMPTS", "3"))# rewriter 최대 시도 횟수
USE_SANDBOX = os.getenv("VERIFIER_SANDBOX", "0") == "1"
SANDBOX_TIMEOUT = 300

TARGET_TOPS = {p.replace("-", "_") for p in TARGET_VERSIONS} # 1.x 버전을 아는 최상위 패키지
EVIDENCE_FAULT_TYPES = {"import_failed"} # 근거 자체가 틀린 오류 -> exclude_ids


# 결과 항목

def issue(type_: str, message: str, *, old_line=None, new_line=None, evidence_id=None, path=None) -> dict:
    """errors / warnings 공통 형식. message는 rewriter 재시도 프롬프트에 그대로 들어가므로 한국어로."""
    return {"type": type_, "message": message, "old_line": old_line, "new_line": new_line,
            "evidence_id": evidence_id, "path": path}


# 1. 문법

def check_syntax(new_code: str) -> tuple[ast.AST | None, list[dict]]:
    try:
        return ast.parse(new_code), []
    except SyntaxError as e:
        return None, [issue("syntax_error", f"문법 오류: {e.msg}", new_line=e.lineno)]

# 2. 근거 ID

def _is_unused_import_removal(change: dict, used_names: set[str] | None) -> bool:
    """안 쓰게 된 import 줄을 지운 기록인가. 이런 삭제는 다른 변경의 결과라 근거 문서가 따로 없다."""
    if used_names is None or (change.get("new") or "").strip():
        return False  # 새 코드를 파싱 못 했거나, 지운 게 아니라 바꾼 기록이면 대상 아님
    try:
        nodes = ast.parse((change.get("old") or "").strip()).body
    except SyntaxError:
        return False
    if not nodes or not all(isinstance(n, (ast.Import, ast.ImportFrom)) for n in nodes):
        return False  # import 줄만 해당함
    names = {(a.asname or a.name).split(".")[0] for n in nodes for a in n.names}
    return not (names & used_names)  # 지운 이름을 새 코드가 아직 쓰면 면제 안 함 (NameError 방지)


def check_evidence_ids(changes: list[dict], shown_ids: list[str] | None, evidences: list[dict],
                       new_code: str | None = None) -> list[dict]:
    """근거 ID를 '이번 프롬프트에 실제로 보여준 근거' 기준으로 검사한다.
    evidences 전체로 검사하면, 피드백에 보였던 이전 ID를 LLM이 복사해도(내용은 못 봤는데) 통과된다.
    예외: 안 쓰게 된 import 줄의 삭제는 근거 ID가 없어도 된다 (unused_import 오류가 시킨 일이므로)."""
    all_ids = {e["evidence_id"] for e in evidences}
    shown = set(shown_ids) if shown_ids is not None else all_ids   # 구버전 rewriter 호환
    try:
        used_names = {n.id for n in ast.walk(ast.parse(new_code)) if isinstance(n, ast.Name)} if new_code is not None else None
    except SyntaxError:
        used_names = None  # 문법 오류면 예외 없이 엄격하게 검사함
    errors = []
    for c in changes:
        ids = c.get("evidence_ids") or []
        if not ids and _is_unused_import_removal(c, used_names):
            continue  # 안 쓰게 된 import 삭제는 근거 없이 허용
        if not ids:
            errors.append(issue("missing_evidence", "변경에 근거 ID가 없습니다. 근거가 없으면 바꾸지 말고 unresolved에 적으세요.",
                                old_line=c.get("old_line")))
        for eid in ids:
            if eid in shown:
                continue
            if eid in all_ids:
                errors.append(issue("evidence_not_shown", "이 근거는 이번 EVIDENCE에 없었습니다. EVIDENCE에 있는 ID만 쓰세요.",
                                    old_line=c.get("old_line"), evidence_id=eid))
            else:
                errors.append(issue("unknown_evidence_id", "존재하지 않는 근거 ID입니다.",
                                    old_line=c.get("old_line"), evidence_id=eid))
    return errors


# 3. 변경 기록 <-> 실제 코드

def _norm_lines(text: str) -> list[str]:
    """비교용: 앞뒤 공백 제거, 빈 줄 제외."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def check_changes(old_code: str, new_code: str, changes: list[dict]) -> list[dict]:
    """rewriter가 적은 변경 기록이 실제 코드와 맞는지 본다.
    - old_line_mismatch: 원본에 없는 줄을 '바꿨다'고 주장 (원문 지어내기)
    - change_not_applied: 바꿨다고 기록했는데 결과 코드에 그 줄이 없음
    - unrecorded_change: 기록(=근거) 없이 바뀐 줄 → 근거 없는 변경이므로 오류"""
    errors = []
    old_lines = old_code.splitlines()
    new_set = set(_norm_lines(new_code))

    recorded_old, recorded_new = set(), set()
    for c in changes:
        old, new, ln = c.get("old") or "", c.get("new") or "", c.get("old_line")
        recorded_old.update(_norm_lines(old))
        recorded_new.update(_norm_lines(new))

        first_old = (_norm_lines(old) or [""])[0]
        if ln is not None and first_old:
            if not 1 <= ln <= len(old_lines):
                errors.append(issue("old_line_mismatch", f"old_line {ln}은 원본 코드 범위를 벗어납니다.", old_line=ln))
            elif old_lines[ln - 1].strip() != first_old:
                errors.append(issue("old_line_mismatch",
                                    f"원본 {ln}번 줄은 {old_lines[ln - 1].strip()!r}인데 old에는 {first_old!r}로 적었습니다.",
                                    old_line=ln))
        missing = [line for line in _norm_lines(new) if line not in new_set]
        if missing:
            errors.append(issue("change_not_applied", f"변경 기록의 새 코드가 new_code에 없습니다: {missing[0]!r}",
                                old_line=ln))

    # 실제 diff 중 기록되지 않은 줄
    old_n, new_n = _norm_lines(old_code), _norm_lines(new_code)
    matcher = difflib.SequenceMatcher(a=old_n, b=new_n, autojunk=False)
    for tag, i1, i2, j1, j2 in matcher.get_opcodes():
        if tag == "equal":
            continue
        for line in new_n[j1:j2]:
            if line not in recorded_new:
                errors.append(issue("unrecorded_change", f"changes에 기록되지 않은 새 줄입니다: {line!r}"))
        for line in old_n[i1:i2]:
            if line not in recorded_old and line not in new_set:
                errors.append(issue("unrecorded_change", f"changes에 기록 없이 사라진 줄입니다: {line!r}"))
    return errors


# import 수집

def collect_imports(tree: ast.AST) -> list[tuple[str, int, bool]]:
    """(경로, 줄 번호, 모듈인지) 목록. langchain / langgraph 계열만."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, node.lineno, True) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out += [(f"{node.module}.{a.name}", node.lineno, False) for a in node.names if a.name != "*"]
    return [x for x in out if x[0].startswith(("langchain", "langgraph"))]


# 4. 구버전 import 잔존

def check_legacy_imports(imports) -> tuple[list[dict], list[dict], set[str]]:
    """대응표(import_map)에 '구 경로'로 등록된 경로가 남았는지 본다.
    대응표에 1.x 경로가 있으면 경로 교체에는 사용법 근거가 필요 없으므로(프롬프트 규칙 1, 2(b), 7)
    남아 있으면 rewriter가 근거를 놓친 것 → 오류. 1.x 경로가 없으면(unresolved) 바꿀 수 없으므로 경고.
    대응표 레코드 ID는 근거 탓이 아니므로 exclude 대상이 아니다(오류 유형이 import_failed가 아님).
    반환: (errors, warnings, 여기서 이미 판정한 경로 → 5번에서 다시 검사하지 않음)"""
    errors, warnings, handled = [], [], set()
    for path, lineno, _ in imports:
        hit = lookup(path)
        if hit is None:
            continue
        handled.add(path)
        rec_id = hit.record["id"]
        if hit.new is None or hit.record.get("kind") == "unresolved":
            warnings.append(issue("no_1x_path", "1.x 대응 경로가 없는 구버전 import입니다. 수동 확인이 필요합니다.",
                                  new_line=lineno, evidence_id=rec_id, path=path))
        else:
            errors.append(issue("legacy_import_remaining",
                                f"구버전 import가 남았습니다. 대응표의 1.x 경로는 {hit.new} 입니다.",
                                new_line=lineno, evidence_id=rec_id, path=path))
    return errors, warnings, handled


# 5. import 존재

@lru_cache(maxsize=1)
def _target_symbols() -> tuple[frozenset[str], frozenset[str]] | None:
    """1.x 심볼 덤프 → (심볼 경로 집합, 모듈 집합). 덤프가 없으면 None."""
    paths, modules = set(), set()
    for package, version in TARGET_VERSIONS.items():
        f = symbols_path(package, version)
        if not f.exists():
            return None
        with f.open(encoding="utf-8") as fh:
            for line in fh:
                rec = json.loads(line)
                paths.add(rec["path"])
                mod = rec.get("module") or rec["path"].rpartition(".")[0]
                parts = mod.split(".")
                modules.update(".".join(parts[:i]) for i in range(1, len(parts) + 1))
    return frozenset(paths), frozenset(modules)


def _exists_static(path: str) -> bool | None:
    """True/False, 또는 판단 불가(None: 덤프 없음 / 1.x 버전을 모르는 패키지)."""
    table = _target_symbols()
    if table is None or path.split(".")[0] not in TARGET_TOPS:
        return None
    paths, modules = table
    return path in paths or path in modules


def _sandbox_import(targets: list[tuple[str, bool]]) -> dict[str, str | None] | None:
    """uv 격리 환경에 1.x 패키지를 설치해 실제로 import 한다. 실패하면 None (정적 검사로 대체)."""
    from src.rag.import_map.build_import_map import IMPORT_CHECK  # 대응표 빌드 때와 같은 검사 스크립트

    packages = [f"{p}=={v}" for p, v in TARGET_VERSIONS.items()] + ["pydantic"]
    payload = [(p, "module" if is_mod else "symbol") for p, is_mod in targets]
    with tempfile.TemporaryDirectory() as tmp:
        inp, out = os.path.join(tmp, "in.json"), os.path.join(tmp, "out.json")
        with open(inp, "w", encoding="utf-8") as f:
            json.dump(payload, f)
        cmd = ["uv", "run", "--isolated", "--no-project", "--python", PYTHON_VERSION]
        for pkg in packages:
            cmd += ["--with", pkg]
        cmd += ["python", "-c", IMPORT_CHECK, inp, out]
        try:
            subprocess.run(cmd, check=True, cwd=tmp, capture_output=True, timeout=SANDBOX_TIMEOUT)
            with open(out, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return None


def _evidence_for(path: str, evidences: list[dict], shown: set[str]) -> dict | None:
    """이 import 경로를 1.x 경로로 제시한 import_map 근거(보여준 것 중)."""
    for e in evidences:
        if e.get("source") == "import_map" and e["evidence_id"] in shown and e.get("new") == path:
            return e
    return None


def loose_key(path: str) -> tuple[str, str]:
    """langchain_openai.chat_models.base.ChatOpenAI 와 langchain_openai.ChatOpenAI 를 같게 본다 (hybrid.py와 같은 규칙)."""
    return path.split(".")[0], path.rsplit(".", 1)[-1]


def grounded_keys(evidences: list[dict], shown: set[str]) -> set[tuple[str, str]]:
    """이번 프롬프트에 보여준 근거가 실제로 언급한 import 경로.
    대응표 근거는 1.x 경로(new), 문서 근거는 본문 코드 예시의 import 문."""
    keys = set()
    for e in evidences:
        if e["evidence_id"] not in shown:
            continue
        if e.get("source") == "import_map" and e.get("new"):
            keys.add(loose_key(e["new"]))
        keys.update(loose_key(p) for p in parse_import_paths(e.get("text") or ""))
    return keys


def check_import_exists(imports, handled: set[str], evidences: list[dict], shown: set[str],
                        grounded: set | None = None, old_paths: set | None = None) -> tuple[list[dict], list[dict]]:
    """grounded: 근거가 언급한 경로, old_paths: 원본 코드에 이미 있던 경로.
    - 1.x에 없음                      → 오류 (import_failed)
    - 존재 확인 불가 + 근거도 없음      → 오류 (ungrounded_import: 지어낸 패키지/경로일 수 있음)
    - 존재 확인 불가 + 근거 있음        → 경고 (import_unverified)
    - 존재하지만 근거에 없음            → 경고 (import_not_in_evidence)"""
    errors, warnings = [], []
    pending = []   # 근거로 판정 못 한 경로는 정적/샌드박스 검사
    grounded, old_paths = grounded or set(), old_paths or set()

    for path, lineno, is_mod in imports:
        if path in handled:
            continue
        e = _evidence_for(path, evidences, shown)
        status = e.get("import_status") if e else None
        if status == "ok":
            continue
        if status == "missing_package":
            pkg = path.split(".")[0].replace("_", "-")
            warnings.append(issue("install_required", f"경로는 맞지만 {pkg} 설치가 필요합니다.",
                                  new_line=lineno, evidence_id=e["evidence_id"], path=path))
            continue
        if status in ("error", "missing_dependency"):
            errors.append(issue("import_failed", f"대응표 빌드 때 import 검사에서 실패한 경로입니다({status}). 다른 근거를 쓰세요.",
                                new_line=lineno, evidence_id=e["evidence_id"], path=path))
            continue
        pending.append((path, lineno, is_mod, e))

    results = _sandbox_import([(p, m) for p, _, m, _ in pending]) if USE_SANDBOX and pending else None
    for path, lineno, is_mod, e in pending:
        eid = e["evidence_id"] if e else None
        if results is not None and path in results:
            ok, detail = results[path] is None, results[path]
        else:
            ok, detail = _exists_static(path), None
        has_source = e is not None or path in old_paths or loose_key(path) in grounded
        if ok is None:
            if has_source:
                warnings.append(issue("import_unverified", "1.x 존재 여부를 확인할 수 없는 경로입니다(심볼 덤프 없음 또는 대상 외 패키지).",
                                      new_line=lineno, evidence_id=eid, path=path))
            else:
                errors.append(issue("ungrounded_import",
                                    f"EVIDENCE에 없고 1.x 존재 여부도 확인할 수 없는 import입니다: {path}. 지어낸 경로일 수 있습니다. EVIDENCE에 나온 경로만 쓰세요.",
                                    new_line=lineno, path=path))
        elif not ok:
            msg = f"1.x에 없는 import 경로입니다: {path}" + (f" ({detail})" if detail else "")
            if eid is None:
                msg += ". EVIDENCE에 나온 경로만 쓰세요."
            errors.append(issue("import_failed", msg, new_line=lineno, evidence_id=eid, path=path))
        elif not has_source:
            warnings.append(issue("import_not_in_evidence", "1.x에 존재하지만 이번 EVIDENCE에는 나오지 않은 경로입니다. 근거를 확인하세요.",
                                  new_line=lineno, path=path))
    return errors, warnings


# 6. 구버전 메서드 잔존 (경고)

def _call_label(rec: dict) -> str:
    """__call__ 은 'obj(...)' 형태라 클래스 이름과 붙이면 'BaseChatModelobj(...)'가 된다."""
    if rec["call"].startswith("."):
        return f"{rec['class']}{rec['call']}"
    return f"{rec['class']} 객체 직접 호출 {rec['call']}"


def check_legacy_methods(new_code: str) -> list[dict]:
    """method_map은 메서드 '이름'만으로 찾으므로(sklearn model.predict도 걸림) 오류로 막지 않고 경고만 남긴다.
    오류로 막으면 정상적으로 남긴 줄 때문에 재시도가 반복된다."""
    warnings, seen = [], set()
    lines = new_code.splitlines()
    for rec in lookup_methods(new_code):
        method = rec["method"]
        if method in seen:
            continue
        seen.add(method)
        pattern = re.compile(r"\.%s\s*\(" % re.escape(method)) if method != "__call__" else None
        line_no = next((i for i, l in enumerate(lines, 1) if pattern and pattern.search(l)), None)
        warnings.append(issue("legacy_method_remaining",
                              f"구버전 호출 {_call_label(rec)}이 남았을 수 있습니다(1.x: {rec['status_1x']}). "
                              f"LangChain 객체라면 {rec.get('alternative') or '대체 방법'}으로 바꿔야 합니다.",
                              new_line=line_no, evidence_id=rec["id"]))
    return warnings


# 7. 안 쓰는 import

def check_unused_imports(tree: ast.AST, old_code: str) -> tuple[list[dict], list[dict]]:
    """import했지만 코드에서 쓰이지 않는 langchain / langgraph 이름을 찾는다.
    - 원래 코드에서 쓰던 이름 → 오류 (변환하고 남은 import. 예: LLMChain을 LCEL로 바꾸고
      from langchain_classic.chains import LLMChain이 남음 → 불필요한 langchain-classic 설치까지 요구하게 됨)
    - 원래 코드에서도 안 쓰던 이름 → 경고 (사용자 코드 그대로이므로 재시도 사유가 아님)"""
    used = {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)}  # 새 코드에서 실제로 참조된 이름
    try:
        old_used = {n.id for n in ast.walk(ast.parse(old_code)) if isinstance(n, ast.Name)}  # 원래 코드에서 쓰던 이름
    except SyntaxError:
        old_used = set()

    errors, warnings = [], []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                and node.module.startswith(("langchain", "langgraph"))):
            continue  # from langchain... import 형태만 검사함
        for a in node.names:
            name = a.asname or a.name  # as 별칭이 있으면 별칭으로 쓰임
            if a.name == "*" or name in used:
                continue
            target = errors if name in old_used else warnings  # 원래 쓰던 이름이면 변환 잔재라 오류
            target.append(issue("unused_import",
                                f"{name}을(를) import했지만 쓰지 않습니다. 이 import 줄을 지우고 changes에 삭제를 기록하세요(new는 빈 문자열, evidence_ids는 비워도 됨).",
                                new_line=node.lineno, path=f"{node.module}.{a.name}"))
    return errors, warnings


# 8. 반환값 보존

STR_RETURN_NOTE = re.compile(r"returned (only )?(a|the output) string", re.IGNORECASE)


def check_return_type(old_code: str, tree: ast.AST) -> list[dict]:
    """chain.run(...) / llm.predict(...)는 문자열을 돌려줬다. 이걸 LCEL(prompt | llm)로 바꾸고
    StrOutputParser()도 .content도 없으면 invoke 결과가 AIMessage가 되어 동작이 바뀐다 (프롬프트 규칙 3 위반).
    method_map Note에 'returned ... string'이 적힌 호출만 대상으로 한다."""
    str_calls = [r for r in lookup_methods(old_code) if STR_RETURN_NOTE.search(r.get("note") or "")]
    if not str_calls:
        return []  # 원래 코드에 문자열 반환 호출이 없으면 검사 안 함
    has_pipe = any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr) for n in ast.walk(tree))
    has_parser = any(isinstance(n, ast.Name) and n.id.endswith("Parser") for n in ast.walk(tree))
    has_content = any(isinstance(n, ast.Attribute) and n.attr == "content" for n in ast.walk(tree))
    if not has_pipe or has_parser or has_content:
        return []  # LCEL이 아니거나, 파서/.content로 문자열을 꺼내면 정상
    rec = str_calls[0]
    return [issue("return_type_changed",
                  f"원래 {_call_label(rec)}은 문자열을 반환했는데, 바꾼 LCEL 체인은 출력 파서가 없어 AIMessage를 반환합니다. "
                  f"근거 Note대로 체인 끝에 StrOutputParser()를 붙이고 그 import도 changes에 기록하세요.",
                  evidence_id=rec["id"])]


# verify 함수 

def verify(
    old_code: str,
    new_code: str,
    changes: list[dict],
    evidences: list[dict],
    shown_evidence_ids: list[str] | None = None,
    unresolved: list[dict] | None = None,
    rewrite_failed: bool = False,
) -> dict:
    unresolved = unresolved or []
    shown = set(shown_evidence_ids) if shown_evidence_ids is not None else {e["evidence_id"] for e in evidences}
    errors, warnings = [], []

    if rewrite_failed:   # LLM 호출 실패로 원본이 그대로 돌아온 경우: 구버전 메서드만 있는 코드는 아래 검사를 우연히 통과한다
        errors.append(issue("rewrite_failed", "rewriter가 결과를 만들지 못했습니다(LLM 호출 실패). 다시 시도합니다."))
    if not USE_SANDBOX and _target_symbols() is None:
        warnings.append(issue("import_check_skipped", "1.x 심볼 덤프(data/raw/symbols)가 없어 import 존재 검사를 건너뜁니다."))
    try:
        old_paths = {p for p, _, _ in collect_imports(ast.parse(old_code))}
    except SyntaxError:
        old_paths = set()

    tree, syntax_errors = check_syntax(new_code)                       # 1
    errors += syntax_errors
    errors += check_evidence_ids(changes, shown_evidence_ids, evidences, new_code)  # 2
    errors += check_changes(old_code, new_code, changes)               # 3

    if tree is not None:                                               # 문법이 맞을 때만 import 분석 가능
        imports = collect_imports(tree)
        e4, w4, handled = check_legacy_imports(imports)                # 4
        e5, w5 = check_import_exists(imports, handled, evidences, shown, grounded_keys(evidences, shown), old_paths)  # 5
        errors += e4 + e5
        warnings += w4 + w5 + check_legacy_methods(new_code)           # 6
        e7, w7 = check_unused_imports(tree, old_code)                  # 7
        errors += e7  # 변환 잔재 import는 재시도시킴
        errors += check_return_type(old_code, tree)                    # 8
        warnings += w7

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "errors": len(errors),
            "warnings": len(warnings),
            "changes": len(changes),
            "unresolved": len(unresolved),
            "import_check": "sandbox" if USE_SANDBOX else ("static" if _target_symbols() is not None else "skipped"),
        },
    }


def faulty_evidence_ids(errors: list[dict]) -> list[str]:
    """근거 자체가 틀린 오류의 근거 ID만. 다음 검색에서 제외된다."""
    return sorted({e["evidence_id"] for e in errors if e["type"] in EVIDENCE_FAULT_TYPES and e["evidence_id"]})


# LangGraph 노드 + 분기

def verifier_node(state: MigrationState) -> dict:
    result = verify(
        old_code=state.get("old_code", ""),
        new_code=state.get("new_code", ""),
        changes=state.get("changes", []),
        evidences=state.get("evidences", []),
        shown_evidence_ids=state.get("shown_evidence_ids"),
        unresolved=state.get("unresolved", []),
        rewrite_failed=state.get("rewrite_failed", False),
    )
    return {
        "verify_result": result,
        "attempt": state.get("attempt", 0) + 1,
        "exclude_ids": faulty_evidence_ids(result["errors"]),   # reducer(merge_ids)가 중복 없이 누적한다
    }


def route_after_verify(state: MigrationState) -> str:
    """supervisor에서: builder.add_conditional_edges("verifier", route_after_verify,
                                                    {"retry": "retriever", "done": "report"})"""
    if state["verify_result"]["passed"] or state.get("attempt", 0) >= MAX_ATTEMPTS:
        return "done"
    return "retry"


# test code 

SAMPLE_OLD = '''from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

llm = ChatOpenAI(temperature=0)
prompt = PromptTemplate.from_template("{product}을 만드는 회사 이름을 지어줘")
chain = LLMChain(llm=llm, prompt=prompt)
print(chain.run(product="양말"))'''

SAMPLE_NEW = '''from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatOpenAI(temperature=0)
prompt = PromptTemplate.from_template("{product}을 만드는 회사 이름을 지어줘")
chain = prompt | llm | StrOutputParser()
print(chain.invoke({"product": "양말"}))'''


def _main():
    from src.rag.retrieval.import_lookup import parse_import_paths

    evidences = []
    for path in parse_import_paths(SAMPLE_OLD):
        hit = lookup(path)
        if hit:
            evidences.append({"evidence_id": hit.record["id"], "source": "import_map", "old": path, "new": hit.new,
                              "kind": hit.record["kind"], "import_status": hit.record.get("import_status")})
    by_old = {e["old"]: e["evidence_id"] for e in evidences}
    changes = [
        {"old_line": 1, "old": "from langchain.chat_models import ChatOpenAI",
         "new": "from langchain_openai import ChatOpenAI", "evidence_ids": [by_old.get("langchain.chat_models.ChatOpenAI", "?")]},
        {"old_line": 2, "old": "from langchain.chains import LLMChain", "new": "", "evidence_ids": [by_old.get("langchain.chains.LLMChain", "?")]},
        {"old_line": 3, "old": "from langchain.prompts import PromptTemplate",
         "new": "from langchain_core.prompts import PromptTemplate\nfrom langchain_core.output_parsers import StrOutputParser",
         "evidence_ids": [by_old.get("langchain.prompts.PromptTemplate", "?")]},
        {"old_line": 7, "old": "chain = LLMChain(llm=llm, prompt=prompt)", "new": "chain = prompt | llm | StrOutputParser()",
         "evidence_ids": [by_old.get("langchain.chains.LLMChain", "?")]},
        {"old_line": 8, "old": 'print(chain.run(product="양말"))', "new": 'print(chain.invoke({"product": "양말"}))',
         "evidence_ids": [by_old.get("langchain.chains.LLMChain", "?")]},
    ]
    result = verify(SAMPLE_OLD, SAMPLE_NEW, changes, evidences)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()