"""verifier 노드: rewriter 결과 검사 (LLM 없음)

검사 항목 (error는 재시도 사유 / warning은 보고서용)
    1. 문법          new_code가 파싱되는가                                       syntax_error
    2. 근거 ID       changes의 근거 ID가 '이번 프롬프트에 보여준 근거'에 있는가     missing_evidence / evidence_not_shown / unknown_evidence_id
    3. 변경 기록     old가 원본 그 줄과 같은가, new가 결과 코드에 있는가            old_line_mismatch / change_not_applied
                     기록 없이 바뀐 줄이 있는가 (근거 없는 변경 = 환각)               unrecorded_change
                     ※ rewriter의 reconcile_changes()가 changes를 실제 diff에 맞춰 주므로 여기는 안전망이다
    4. 구버전 import 대응표의 구 경로가 남았는가                                     legacy_import_remaining  (경고: no_1x_path, mapping_unusable)
    5. import 존재   새 import 경로가 1.x에 실제로 있는가, 근거가 있는가              import_failed / ungrounded_import
                                                                                  (경고: install_required, import_unverified, import_not_in_evidence)
    6. 구버전 메서드 대응표의 메서드 호출이 남았는가 (이름만으로 찾으므로 경고만)      legacy_method_remaining
    7. 안 쓰는 import 원래 쓰던 이름의 import가 변환 후 안 쓰이는가                  unused_import  (원래부터 안 쓰던 것은 경고)
    8. 반환값 보존   문자열을 돌려주던 .run/.predict를 바꾸면서 문자열을 잃었는가     return_type_changed
                     (a) LCEL로 바꾸면서 출력 파서도 .content도 없이 끝냄
                     (b) 같은 객체의 .invoke로만 바꾸고 결과를 꺼내지 않음 (체인 → dict[출력 키], 채팅 모델 → .content)
    9. 정의 안 된 이름 import도 정의도 안 한 이름을 쓰는가 (NameError)               undefined_name  (원래도 정의 안 됐으면 경고)
   10. 출력 꺼내기   LCEL 체인 invoke 결과를 ['text']처럼 꺼내는가 (TypeError)        invoke_output_subscript
   11. 체인 입출력 키 레거시 체인 invoke의 입력·출력 키가 실제 키와 같은가            chain_io_key

import 존재 확인 순서 (5번)
    a. 그 경로를 준 import_map 근거의 import_status (대응표 빌드 때 실제 import 결과)
    b. 없으면 1.x 심볼 덤프(data/raw/symbols/{패키지}-{1.x 버전}.jsonl)로 정적 확인
    c. VERIFIER_SANDBOX=1이면 b 대신 uv 격리 환경에 1.x 패키지를 설치해 실제로 import

재시도 연결
    - exclude_ids에는 '근거 자체가 틀린' 오류(import_failed + 근거 ID 있음)만 넣는다.
    - attempt를 1 올리고, route_after_verify()가 다음 경로를 정한다.
        done    통과했거나 MAX_ATTEMPTS에 닿음
        retry   근거를 다시 찾아야 풀리는 오류(NEEDS_RETRIEVAL)가 하나라도 있음 → retriever
        rewrite 그 밖의 오류만 있음 → retriever를 건너뛰고 rewriter로
                (변경 기록·문법 같은 오류에도 매번 검색하면 근거만 11→18→24개로 늘고 노이즈가 커졌다)

state.py
    읽기: evidences, shown_evidence_ids, changes, unresolved, old_code, new_code, rewrite_failed
    쓰기: verify_result, attempt, exclude_ids(merge_ids reducer: 합집합 누적)

단독 실행 (프로젝트 루트, 가상환경 켠 상태. OpenAI 키 불필요):
    python -m src.graph.nodes.verifier_node
    실제 import 검사(PowerShell): $env:VERIFIER_SANDBOX="1"; python -m src.graph.nodes.verifier_node
"""

import ast
import builtins
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

MAX_ATTEMPTS = int(os.getenv("VERIFIER_MAX_ATTEMPTS", "3"))  # rewriter 최대 시도 횟수
USE_SANDBOX = os.getenv("VERIFIER_SANDBOX", "0") == "1"
SANDBOX_TIMEOUT = 300

TARGET_TOPS = {p.replace("-", "_") for p in TARGET_VERSIONS}  # 1.x 버전을 아는 최상위 패키지
LANGCHAIN_TOPS = ("langchain", "langgraph")                     # 검사 대상 패키지 접두어
EVIDENCE_FAULT_TYPES = {"import_failed"}                        # 근거 자체가 틀린 오류 → exclude_ids
NEEDS_RETRIEVAL = {"missing_evidence", "evidence_not_shown", "unknown_evidence_id",  # 근거를 다시 찾아야 풀리는 오류
                   "import_failed", "ungrounded_import"}
INVOKE = ("invoke", "ainvoke")


# 공통

def issue(type_: str, message: str, *, old_line=None, new_line=None, evidence_id=None, path=None) -> dict:
    """errors / warnings 공통 형식. message는 rewriter 재시도 프롬프트에 그대로 들어가므로 한국어로."""
    return {"type": type_, "message": message, "old_line": old_line, "new_line": new_line,
            "evidence_id": evidence_id, "path": path}


def _parse(code: str) -> ast.AST | None:
    try:
        return ast.parse(code)
    except SyntaxError:
        return None


def _names(tree: ast.AST | None) -> set[str]:
    """코드에서 참조된 이름 전체(ast.Name). tree가 None이면 빈 집합."""
    return {n.id for n in ast.walk(tree) if isinstance(n, ast.Name)} if tree is not None else set()


def _norm_lines(text: str) -> list[str]:
    """비교용: 앞뒤 공백 제거, 빈 줄 제외."""
    return [line.strip() for line in text.splitlines() if line.strip()]


def _callee_name(node: ast.AST) -> str:
    """ChatOpenAI(...) → 'ChatOpenAI', parsers.StrOutputParser() → 'StrOutputParser'."""
    if isinstance(node, ast.Call):
        node = node.func
    return node.id if isinstance(node, ast.Name) else node.attr if isinstance(node, ast.Attribute) else ""


def _constructed_class(call: ast.Call) -> str:
    """객체를 만든 클래스 이름. RetrievalQA.from_chain_type(...)처럼 from_* 생성자는 앞의 클래스 이름."""
    f = call.func
    return _callee_name(f.value) if isinstance(f, ast.Attribute) and f.attr.startswith("from_") else _callee_name(call)


def _assigned_value(tree: ast.AST, name: str) -> ast.AST | None:
    """name = ... 중 가장 마지막 할당의 오른쪽 식."""
    found = None
    for n in ast.walk(tree):
        if (isinstance(n, ast.Assign) and len(n.targets) == 1 and isinstance(n.targets[0], ast.Name)
                and n.targets[0].id == name and (found is None or n.lineno > found.lineno)):
            found = n
    return found.value if found else None


def _invoke_calls(tree: ast.AST, named: bool = False) -> list[ast.Call]:
    """x.invoke(...) / x.ainvoke(...) 호출. named=True면 x가 변수 이름인 것만."""
    return [n for n in ast.walk(tree)
            if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in INVOKE
            and (not named or isinstance(n.func.value, ast.Name))]


def _result_uses(call: ast.Call, parent: dict, tree: ast.AST) -> list[ast.AST] | None:
    """invoke 결과를 꺼내 쓰는 노드: x.invoke(...)[k] / x.invoke(...).a / r = x.invoke(...) 뒤의 r[k], r.a.
    8·10·11번이 같이 쓴다. 결과를 버리는 단독 문장이면 None."""
    node, p = call, parent.get(call)
    if isinstance(p, ast.Await):
        node, p = p, parent.get(p)
    if isinstance(p, ast.Expr):
        return None
    if isinstance(p, (ast.Subscript, ast.Attribute)) and p.value is node:
        return [p]
    if isinstance(p, ast.Assign) and len(p.targets) == 1 and isinstance(p.targets[0], ast.Name):
        var = p.targets[0].id
        return [n for n in ast.walk(tree) if isinstance(n, (ast.Subscript, ast.Attribute))
                and isinstance(n.value, ast.Name) and n.value.id == var]
    return []


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
        return False  # 새 코드를 파싱 못 했거나, 지운 게 아니라 바꾼 기록
    tree = _parse((change.get("old") or "").strip())
    nodes = tree.body if tree else []
    if not nodes or not all(isinstance(n, (ast.Import, ast.ImportFrom)) for n in nodes):
        return False  # import 줄만 해당
    names = {(a.asname or a.name).split(".")[0] for n in nodes for a in n.names}
    return not (names & used_names)  # 지운 이름을 새 코드가 아직 쓰면 면제 안 함 (NameError 방지)


def check_evidence_ids(changes: list[dict], shown: set[str], all_ids: set[str],
                       used_names: set[str] | None) -> list[dict]:
    """근거 ID를 '이번 프롬프트에 실제로 보여준 근거(shown)' 기준으로 검사한다.
    evidences 전체로 검사하면 피드백에 보였던 이전 ID를 LLM이 복사해도(내용은 못 봤는데) 통과된다.
    예외: 안 쓰게 된 import 줄의 삭제는 근거 ID가 없어도 된다."""
    errors = []
    for c in changes:
        ids, ln = c.get("evidence_ids") or [], c.get("old_line")
        if not ids:
            if not _is_unused_import_removal(c, used_names):
                errors.append(issue("missing_evidence", "변경에 근거 ID가 없습니다. 근거가 없으면 바꾸지 말고 unresolved에 적으세요.",
                                    old_line=ln))
            continue
        for eid in ids:
            if eid in shown:
                continue
            type_, msg = (("evidence_not_shown", "이 근거는 이번 EVIDENCE에 없었습니다. EVIDENCE에 있는 ID만 쓰세요.")
                          if eid in all_ids else ("unknown_evidence_id", "존재하지 않는 근거 ID입니다."))
            errors.append(issue(type_, msg, old_line=ln, evidence_id=eid))
    return errors


# 3. 변경 기록 <-> 실제 코드

def check_changes(old_code: str, new_code: str, changes: list[dict]) -> list[dict]:
    """- old_line_mismatch: 원본에 없는 줄을 '바꿨다'고 주장 (원문 지어내기)
    - change_not_applied: 바꿨다고 기록했는데 결과 코드에 그 줄이 없음
    - unrecorded_change: 기록(=근거) 없이 바뀐 줄 → 근거 없는 변경이므로 오류"""
    errors, old_lines = [], old_code.splitlines()
    old_n, new_n = _norm_lines(old_code), _norm_lines(new_code)
    new_set = set(new_n)
    recorded_old, recorded_new = set(), set()

    for c in changes:
        old, new, ln = _norm_lines(c.get("old") or ""), _norm_lines(c.get("new") or ""), c.get("old_line")
        recorded_old.update(old)
        recorded_new.update(new)
        if ln is not None and old:
            if not 1 <= ln <= len(old_lines):
                errors.append(issue("old_line_mismatch", f"old_line {ln}은 원본 코드 범위를 벗어납니다.", old_line=ln))
            elif old_lines[ln - 1].strip() != old[0]:
                errors.append(issue("old_line_mismatch",
                                    f"원본 {ln}번 줄은 {old_lines[ln - 1].strip()!r}인데 old에는 {old[0]!r}로 적었습니다.",
                                    old_line=ln))
        missing = [line for line in new if line not in new_set]
        if missing:
            errors.append(issue("change_not_applied", f"변경 기록의 새 코드가 new_code에 없습니다: {missing[0]!r}", old_line=ln))

    for tag, i1, i2, j1, j2 in difflib.SequenceMatcher(a=old_n, b=new_n, autojunk=False).get_opcodes():
        if tag == "equal":
            continue
        errors += [issue("unrecorded_change", f"changes에 기록되지 않은 새 줄입니다: {line!r}")
                   for line in new_n[j1:j2] if line not in recorded_new]
        errors += [issue("unrecorded_change", f"changes에 기록 없이 사라진 줄입니다: {line!r}")
                   for line in old_n[i1:i2] if line not in recorded_old and line not in new_set]
    return errors


# import 수집 (4·5·9번 공통)

def collect_imports(tree: ast.AST) -> list[tuple[str, int, bool]]:
    """(경로, 줄 번호, 모듈인지) 목록. langchain / langgraph 계열만."""
    out = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out += [(a.name, node.lineno, True) for a in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            out += [(f"{node.module}.{a.name}", node.lineno, False) for a in node.names if a.name != "*"]
    return [x for x in out if x[0].startswith(LANGCHAIN_TOPS)]


def evidence_import_paths(evidences: list[dict], shown: set[str]) -> list[tuple[str, str]]:
    """이번에 보여준 근거가 언급한 import 경로 → [(경로, 근거 ID)].
    대응표 근거는 1.x 경로(new), 문서 근거는 본문 코드 예시의 import 문. 5번과 9번이 같이 쓴다."""
    out = []
    for e in evidences:
        if e["evidence_id"] not in shown:
            continue
        if e.get("source") == "import_map" and e.get("new"):
            out.append((e["new"], e["evidence_id"]))
        out += [(p, e["evidence_id"]) for p in parse_import_paths(e.get("text") or "")]
    return out


# 4. 구버전 import 잔존

def check_legacy_imports(imports, exclude_ids: set[str] | frozenset[str] = frozenset()) -> tuple[list[dict], list[dict], set[str]]:
    """대응표에 '구 경로'로 등록된 경로가 남았는지 본다.
    1.x 경로가 있으면 남은 것은 rewriter가 놓친 것 → 오류. 1.x 경로가 없거나 그 경로가 import 안 되면 바꿀 수 없으니 경고.
    반환: (errors, warnings, 여기서 이미 판정한 경로 → 5번에서 다시 검사하지 않음)"""
    errors, warnings, handled = [], [], set()
    for path, lineno, _ in imports:
        hit = lookup(path)
        if hit is None:
            continue
        handled.add(path)
        rec_id = hit.record["id"]
        kw = dict(new_line=lineno, evidence_id=rec_id, path=path)
        if rec_id in exclude_ids or hit.record.get("import_status") in ("error", "missing_dependency"):
            warnings.append(issue("mapping_unusable", "대응표의 1.x 경로가 import 검사에서 실패해 바꾸지 않았습니다. 수동 확인이 필요합니다.", **kw))
        elif hit.new is None or hit.record.get("kind") == "unresolved":
            warnings.append(issue("no_1x_path", "1.x 대응 경로가 없는 구버전 import입니다. 수동 확인이 필요합니다.", **kw))
        else:
            errors.append(issue("legacy_import_remaining", f"구버전 import가 남았습니다. 대응표의 1.x 경로는 {hit.new} 입니다.", **kw))
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
                parts = (rec.get("module") or rec["path"].rpartition(".")[0]).split(".")
                modules.update(".".join(parts[:i]) for i in range(1, len(parts) + 1))
    return frozenset(paths), frozenset(modules)


def _exists_static(path: str) -> bool | None:
    """True/False, 또는 판단 불가(None: 덤프 없음 / 1.x 버전을 모르는 패키지)."""
    table = _target_symbols()
    if table is None or path.split(".")[0] not in TARGET_TOPS:
        return None
    return path in table[0] or path in table[1]


def _sandbox_import(targets: list[tuple[str, bool]]) -> dict[str, str | None] | None:
    """uv 격리 환경에 1.x 패키지를 설치해 실제로 import 한다. 실패하면 None (정적 검사로 대체)."""
    from src.rag.import_map.build_import_map import IMPORT_CHECK  # 대응표 빌드 때와 같은 검사 스크립트

    cmd = ["uv", "run", "--isolated", "--no-project", "--python", PYTHON_VERSION]
    for pkg in [f"{p}=={v}" for p, v in TARGET_VERSIONS.items()] + ["pydantic"]:
        cmd += ["--with", pkg]
    with tempfile.TemporaryDirectory() as tmp:
        inp, out = os.path.join(tmp, "in.json"), os.path.join(tmp, "out.json")
        with open(inp, "w", encoding="utf-8") as f:
            json.dump([(p, "module" if is_mod else "symbol") for p, is_mod in targets], f)
        try:
            subprocess.run(cmd + ["python", "-c", IMPORT_CHECK, inp, out], check=True, cwd=tmp,
                           capture_output=True, timeout=SANDBOX_TIMEOUT)
            with open(out, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, subprocess.SubprocessError, json.JSONDecodeError):
            return None


def loose_key(path: str) -> tuple[str, str]:
    """langchain_openai.chat_models.base.ChatOpenAI 와 langchain_openai.ChatOpenAI 를 같게 본다 (hybrid.py와 같은 규칙)."""
    return path.split(".")[0], path.rsplit(".", 1)[-1]


def check_import_exists(imports, handled: set[str], evidences: list[dict], shown: set[str],
                        grounded: set, old_paths: set) -> tuple[list[dict], list[dict]]:
    """grounded: 근거가 언급한 경로(loose_key), old_paths: 원본 코드에 이미 있던 경로.
    - 1.x에 없음                   → 오류 (import_failed)
    - 존재 확인 불가 + 근거도 없음   → 오류 (ungrounded_import: 지어낸 경로일 수 있음)
    - 존재 확인 불가 + 근거 있음     → 경고 (import_unverified)
    - 존재하지만 근거에 없음         → 경고 (import_not_in_evidence)"""
    errors, warnings, pending = [], [], []   # pending: 근거로 판정 못 해 정적/샌드박스 검사할 경로
    for path, lineno, is_mod in imports:
        if path in handled:
            continue
        e = next((x for x in evidences if x.get("source") == "import_map"
                  and x["evidence_id"] in shown and x.get("new") == path), None)
        status = e.get("import_status") if e else None
        if status == "missing_package":
            warnings.append(issue("install_required", f"경로는 맞지만 {path.split('.')[0].replace('_', '-')} 설치가 필요합니다.",
                                  new_line=lineno, evidence_id=e["evidence_id"], path=path))
        elif status in ("error", "missing_dependency"):
            errors.append(issue("import_failed", f"대응표 빌드 때 import 검사에서 실패한 경로입니다({status}). 다른 근거를 쓰세요.",
                                new_line=lineno, evidence_id=e["evidence_id"], path=path))
        elif status != "ok":
            pending.append((path, lineno, is_mod, e))

    results = _sandbox_import([(p, m) for p, _, m, _ in pending]) if USE_SANDBOX and pending else None
    for path, lineno, is_mod, e in pending:
        eid = e["evidence_id"] if e else None
        ok, detail = (results[path] is None, results[path]) if results is not None and path in results else (_exists_static(path), None)
        has_source = e is not None or path in old_paths or loose_key(path) in grounded
        if ok is None and has_source:
            warnings.append(issue("import_unverified", "1.x 존재 여부를 확인할 수 없는 경로입니다(심볼 덤프 없음 또는 대상 외 패키지).",
                                  new_line=lineno, evidence_id=eid, path=path))
        elif ok is None:
            errors.append(issue("ungrounded_import",
                                f"EVIDENCE에 없고 1.x 존재 여부도 확인할 수 없는 import입니다: {path}. 지어낸 경로일 수 있습니다. EVIDENCE에 나온 경로만 쓰세요.",
                                new_line=lineno, path=path))
        elif not ok:
            msg = f"1.x에 없는 import 경로입니다: {path}" + (f" ({detail})" if detail else "") + ("" if eid else ". EVIDENCE에 나온 경로만 쓰세요.")
            errors.append(issue("import_failed", msg, new_line=lineno, evidence_id=eid, path=path))
        elif not has_source:
            warnings.append(issue("import_not_in_evidence", "1.x에 존재하지만 이번 EVIDENCE에는 나오지 않은 경로입니다. 근거를 확인하세요.",
                                  new_line=lineno, path=path))
    return errors, warnings


# 6. 구버전 메서드 잔존 (경고)

def _call_label(rec: dict) -> str:
    """__call__ 은 'obj(...)' 형태라 클래스 이름과 붙이면 'BaseChatModelobj(...)'가 된다."""
    return f"{rec['class']}{rec['call']}" if rec["call"].startswith(".") else f"{rec['class']} 객체 직접 호출 {rec['call']}"


def check_legacy_methods(new_code: str) -> list[dict]:
    """method_map은 메서드 '이름'만으로 찾으므로(sklearn model.predict도 걸림) 오류로 막지 않고 경고만 남긴다."""
    warnings, seen, lines = [], set(), new_code.splitlines()
    for rec in lookup_methods(new_code):
        method = rec["method"]
        if method in seen:
            continue
        seen.add(method)
        line_no = None
        if method != "__call__":
            pattern = re.compile(r"\.%s\s*\(" % re.escape(method))
            line_no = next((i for i, l in enumerate(lines, 1) if pattern.search(l)), None)
        warnings.append(issue("legacy_method_remaining",
                              f"구버전 호출 {_call_label(rec)}이 남았을 수 있습니다(1.x: {rec['status_1x']}). "
                              f"LangChain 객체라면 {rec.get('alternative') or '대체 방법'}으로 바꿔야 합니다.",
                              new_line=line_no, evidence_id=rec["id"]))
    return warnings


# 7. 안 쓰는 import

def check_unused_imports(tree: ast.AST, used: set[str], old_used: set[str]) -> tuple[list[dict], list[dict]]:
    """import했지만 쓰지 않는 langchain / langgraph 이름. 원래 쓰던 이름이면 변환 잔재라 오류, 원래도 안 쓰던 이름이면 경고.
    rewriter의 drop_leftover_imports()가 같은 기준으로 먼저 정리하므로, 여기 걸리면 그 후처리를 빠져나간 경우다."""
    errors, warnings = [], []
    for node in ast.walk(tree):
        if not (isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                and node.module.startswith(LANGCHAIN_TOPS)):
            continue
        for a in node.names:
            name = a.asname or a.name
            if a.name == "*" or name in used:
                continue
            (errors if name in old_used else warnings).append(issue(
                "unused_import",
                f"{name}을(를) import했지만 쓰지 않습니다. 이 import 줄을 지우고 changes에 삭제를 기록하세요(new는 빈 문자열, evidence_ids는 비워도 됨).",
                new_line=node.lineno, path=f"{node.module}.{a.name}"))
    return errors, warnings


# 8. 반환값 보존

STR_RETURN_NOTE = re.compile(r"returned (only )?(a|the output) string", re.IGNORECASE)

# 레거시 체인(langchain_classic)의 invoke 입력 키·출력 키 (각 클래스의 기본값).
# inputs가 None이면 입력 키가 프롬프트 변수에 따라 달라지므로 검사하지 않는다(LLMChain).
# extra: 출력 키 외에 결과 dict에 들어올 수 있는 키 (memory 기록, 출처 문서 등)
CHAIN_IO_KEYS = {
    "LLMChain":                     {"inputs": None,                         "output": "text",     "extra": set()},
    "ConversationChain":            {"inputs": {"input"},                    "output": "response", "extra": {"history"}},
    "RetrievalQA":                  {"inputs": {"query"},                    "output": "result",   "extra": {"source_documents"}},
    "ConversationalRetrievalChain": {"inputs": {"question", "chat_history"}, "output": "answer",   "extra": {"source_documents", "generated_question"}},
    "RetrievalQAWithSourcesChain":  {"inputs": {"question"},                 "output": "answer",   "extra": {"sources", "source_documents"}},
}


def _object_kind(tree: ast.AST, name: str) -> tuple[str, str] | None:
    """변수가 가리키는 객체의 invoke 결과 형태. ('dict', 클래스명) 체인 / ('message', 클래스명) 채팅 모델 / None 모름.
    | 로 만든 LCEL 체인은 (a)와 10번 검사가 맡는다."""
    value = _assigned_value(tree, name)
    if not isinstance(value, ast.Call):
        return None
    cls = _constructed_class(value)
    if cls.endswith("Chain") or cls in CHAIN_IO_KEYS:
        return "dict", cls
    return ("message", cls) if cls.startswith("Chat") else None


def check_return_type(old_code: str, old_tree: ast.AST | None, tree: ast.AST, parent: dict) -> list[dict]:
    """chain.run(...) / llm.predict(...)는 문자열을 돌려줬다. 바꾼 뒤에도 문자열이어야 한다 (프롬프트 규칙 3).
    method_map Note에 'returned ... string'이 적힌 호출만 대상으로 한다."""
    str_calls = [r for r in lookup_methods(old_code) if STR_RETURN_NOTE.search(r.get("note") or "")]
    if not str_calls:
        return []
    rec, errors = str_calls[0], []

    # (a) LCEL 체인인데 출력 파서도 .content도 없음 → 결과가 AIMessage
    nodes = list(ast.walk(tree))
    if (any(isinstance(n, ast.BinOp) and isinstance(n.op, ast.BitOr) for n in nodes)
            and not any(isinstance(n, ast.Name) and n.id.endswith("Parser") for n in nodes)
            and not any(isinstance(n, ast.Attribute) and n.attr == "content" for n in nodes)):
        errors.append(issue("return_type_changed",
                            f"원래 {_call_label(rec)}은 문자열을 반환했는데, 바꾼 LCEL 체인은 출력 파서가 없어 AIMessage를 반환합니다. "
                            f"근거 Note대로 체인 끝에 StrOutputParser()를 붙이고 그 import도 changes에 기록하세요.",
                            evidence_id=rec["id"]))
    if old_tree is None:
        return errors

    # (b) 같은 변수의 .run/.predict → .invoke 인데 결과를 꺼내지 않음
    methods = {r["method"] for r in str_calls}
    old_calls = {}  # 변수 → 원래 메서드
    for n in ast.walk(old_tree):
        if (isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) and n.func.attr in methods
                and isinstance(n.func.value, ast.Name)):
            old_calls.setdefault(n.func.value.id, n.func.attr)
    reported = set()
    for n in _invoke_calls(tree, named=True):
        var = n.func.value.id
        kind = _object_kind(tree, var) if var in old_calls and var not in reported else None
        if kind is None:
            continue
        uses = _result_uses(n, parent, tree)
        if uses is None or any(isinstance(u, ast.Subscript) if kind[0] == "dict"
                               else isinstance(u, ast.Attribute) and u.attr == "content" for u in uses):
            continue  # 결과를 버리거나 제대로 꺼냄
        reported.add(var)
        before = f"원래 {var}.{old_calls[var]}(...)은 문자열을 반환했는데"
        if kind[0] == "dict":
            key = (CHAIN_IO_KEYS.get(kind[1]) or {}).get("output")
            how = f'{var}.invoke(...)["{key}"]' if key else f"{var}.invoke(...)[출력 키]"
            msg = f"{before}, {kind[1]}.invoke는 입력과 출력이 함께 담긴 dict를 반환합니다(출력이 달라짐). 원래처럼 문자열을 쓰려면 {how}로 꺼내세요."
        else:
            msg = f"{before}, 채팅 모델 {kind[1]}.invoke는 AIMessage를 반환합니다(출력이 달라짐). {var}.invoke(...).content로 문자열을 꺼내세요."
        errors.append(issue("return_type_changed", msg, new_line=n.lineno, evidence_id=rec["id"]))
    return errors


# 9. 정의되지 않은 이름

BUILTIN_NAMES = set(dir(builtins)) | {"__file__", "__name__", "__doc__", "__spec__", "__package__",
                                      "__loader__", "__builtins__", "__path__", "__annotations__"}


def undefined_names(tree: ast.AST) -> dict[str, int]:
    """읽기만 하고 파일 어디에서도 정의하지 않은 이름 → 처음 나온 줄 번호.
    스코프를 따지지 않고 파일 전체에서 한 번이라도 정의되면 정의된 것으로 본다(오탐을 줄이려고 느슨하게).
    from x import * 가 있으면 어떤 이름이 들어왔는지 알 수 없어 검사하지 않는다."""
    bound = set(BUILTIN_NAMES)
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and not isinstance(n.ctx, ast.Load):
            bound.add(n.id)
        elif isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            bound.add(n.name)
        elif isinstance(n, ast.arg):
            bound.add(n.arg)
        elif isinstance(n, (ast.Import, ast.ImportFrom)):
            if any(a.name == "*" for a in n.names):
                return {}
            bound.update((a.asname or a.name).split(".")[0] for a in n.names)
        elif isinstance(n, (ast.Global, ast.Nonlocal)):
            bound.update(n.names)
        elif isinstance(n, ast.ExceptHandler) or type(n).__name__ in ("MatchAs", "MatchStar", "MatchMapping"):
            name = getattr(n, "name", None) or getattr(n, "rest", None)  # except as / match 패턴 이름
            if name:
                bound.add(name)
    out: dict[str, int] = {}
    for n in ast.walk(tree):
        if isinstance(n, ast.Name) and isinstance(n.ctx, ast.Load) and n.id not in bound:
            out[n.id] = min(out.get(n.id, n.lineno), n.lineno)
    return out


def check_undefined_names(tree: ast.AST, old_tree: ast.AST | None,
                          ev_paths: list[tuple[str, str]]) -> tuple[list[dict], list[dict]]:
    """새 코드에서 정의 안 된 이름. 근거에 그 이름의 import 경로가 있으면 '어떤 줄을 넣으면 되는지'까지 피드백에 적는다.
    원래 코드에서도 정의 안 된 이름은 경고 (코드 조각이라 다른 곳에서 정의됐을 수 있음)."""
    old_undefined = set(undefined_names(old_tree)) if old_tree is not None else set()
    hints: dict[str, tuple[str, str]] = {}  # 이름 → (import 문, 근거 ID)
    for path, eid in ev_paths:
        module, _, name = path.rpartition(".")
        if module.startswith(LANGCHAIN_TOPS):
            hints.setdefault(name, (f"from {module} import {name}", eid))

    errors, warnings = [], []
    for name, line in sorted(undefined_names(tree).items(), key=lambda x: x[1]):
        if name in old_undefined:
            warnings.append(issue("undefined_name", f"{name}이(가) 정의되지 않았습니다. 원래 코드에서도 정의되지 않은 이름이라 그대로 두었습니다.",
                                  new_line=line))
            continue
        hint = hints.get(name)
        msg = f"{name}을(를) 쓰지만 import하거나 정의하지 않았습니다(실행하면 NameError). " + (
            f"근거 [{hint[1]}]에 나온 `{hint[0]}` 줄을 추가하고, 그 추가를 changes에 기록하세요(evidence_ids에 {hint[1]})." if hint else
            "EVIDENCE에 나온 import 경로로 추가하고 changes에 기록하세요. EVIDENCE에 경로가 없으면 이 변경을 되돌리고 unresolved에 적으세요.")
        errors.append(issue("undefined_name", msg, new_line=line, evidence_id=hint[1] if hint else None))
    return errors, warnings


# 10. LCEL 체인 출력 꺼내기

def _pipeline_output(expr: ast.AST, tree: ast.AST) -> str | None:
    """| 로 만든 LCEL 체인의 출력 종류. 'str'(StrOutputParser로 끝남) / 'message'(채팅 모델로 끝남) / None(판단 안 함)."""
    if isinstance(expr, ast.Name):
        expr = _assigned_value(tree, expr.id)
    if not (isinstance(expr, ast.BinOp) and isinstance(expr.op, ast.BitOr)):
        return None  # | 체인이 아니면(LLMChain 등) 검사하지 않음
    last = expr.right
    if isinstance(last, ast.Name):
        last = _assigned_value(tree, last.id)  # prompt | llm 의 llm = ChatOpenAI(...)
        if isinstance(last, ast.Call) and _callee_name(last).startswith("Chat"):
            return "message"
        return None
    if isinstance(last, ast.Call):
        if _callee_name(last).endswith("StrOutputParser"):
            return "str"
        if _callee_name(last).startswith("Chat"):
            return "message"
    return None


def _lcel_evidence_id(evidences: list[dict], shown: set[str]) -> str | None:
    """["text"] 수정의 근거로 쓸, 이번에 보여 준 근거 ID. method_map 근거 → 없으면 LLMChain import_map 근거.
    피드백에 근거 ID가 없으면 LLM이 ["text"]를 지운 변경에 근거를 못 달아 2번에 걸리고, 재시도해도 통과할 수 없다."""
    shown_ev = [e for e in evidences if e.get("evidence_id") in shown]
    e = (next((e for e in shown_ev if e.get("source") == "method_map"), None)
         or next((e for e in shown_ev if e.get("source") == "import_map" and (e.get("old") or "").endswith("LLMChain")), None))
    return e["evidence_id"] if e else None


def check_invoke_subscript(tree: ast.AST, parent: dict, evidence_id: str | None = None) -> list[dict]:
    """chain.invoke(...)["text"] / result = chain.invoke(...) → result["text"] 를 찾는다.
    구버전 LLMChain.invoke는 dict라 ['text']가 맞았지만, LCEL 체인은 문자열(StrOutputParser)이나 AIMessage(모델)를 돌려줘 TypeError."""
    errors = []
    for call in _invoke_calls(tree):
        kind = _pipeline_output(call.func.value, tree)
        if kind is None:
            continue
        for n in _result_uses(call, parent, tree) or []:
            if not (isinstance(n, ast.Subscript) and isinstance(n.ctx, ast.Load)):
                continue
            key = ast.unparse(n.slice)
            msg = (f"체인이 StrOutputParser()로 끝나서 invoke 결과가 이미 문자열인데 [{key}]로 꺼내고 있습니다(실행하면 TypeError). "
                   f"구버전 LLMChain 결과(dict)를 꺼내던 방식이 남은 것이니 [{key}]를 지우고 결과를 그대로 쓰세요." if kind == "str" else
                   f"체인이 채팅 모델로 끝나서 invoke 결과가 AIMessage인데 [{key}]로 꺼내고 있습니다"
                   f"(실행하면 TypeError: 'AIMessage' object is not subscriptable). 체인 끝에 | StrOutputParser()를 붙이고 [{key}]를 지우세요. "
                   f"StrOutputParser의 import 줄도 추가하고 두 변경 모두 changes에 기록하세요.")
            if evidence_id:
                msg += f" [{key}]를 지운 변경은 근거 [{evidence_id}]로 기록하세요(evidence_ids에 {evidence_id})."
            errors.append(issue("invoke_output_subscript", msg, new_line=n.lineno, evidence_id=evidence_id))
    return errors


# 11. 레거시 체인 입출력 키

def check_chain_io_keys(tree: ast.AST, parent: dict) -> list[dict]:
    """레거시 체인 invoke의 입력·출력 키가 그 클래스의 실제 키와 맞는지 본다 (CHAIN_IO_KEYS).
    LLM이 RetrievalQA에 {"input": ...}을 넣고 ["output"]으로 꺼낸 일이 실제로 있었다(정답: "query" / "result")."""
    errors = []
    for n in _invoke_calls(tree, named=True):
        var = n.func.value.id
        value = _assigned_value(tree, var)
        cls = _constructed_class(value) if isinstance(value, ast.Call) else ""
        info = CHAIN_IO_KEYS.get(cls)
        if info is None or info["inputs"] is None:
            continue
        inputs = sorted(info["inputs"])
        example = f'{var}.invoke({{"{inputs[0]}": ...}})["{info["output"]}"]'

        if n.args and isinstance(n.args[0], ast.Dict):  # 입력 키: dict를 직접 쓴 경우만
            keys = {k.value for k in n.args[0].keys if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            wrong = sorted(keys - info["inputs"])
            if wrong:
                errors.append(issue("chain_io_key", f"{cls}의 입력 키는 {inputs}인데 {wrong}을(를) 넣었습니다"
                                    f"(실행하면 ValueError: Missing some input keys). {example}처럼 쓰세요.", new_line=n.lineno))

        allowed = info["inputs"] | {info["output"]} | info["extra"]  # 출력 키: 결과 dict에서 꺼낸 문자열 키
        for s in _result_uses(n, parent, tree) or []:
            key = s.slice.value if isinstance(s, ast.Subscript) and isinstance(s.slice, ast.Constant) else None
            if isinstance(key, str) and key not in allowed:
                errors.append(issue("chain_io_key", f'{cls}의 출력 키는 "{info["output"]}"인데 ["{key}"]로 꺼내고 있습니다'
                                    f"(실행하면 KeyError). {example}처럼 쓰세요.", new_line=s.lineno))
    return errors


# verify 함수

def verify(
    old_code: str,
    new_code: str,
    changes: list[dict],
    evidences: list[dict],
    shown_evidence_ids: list[str] | None = None,
    unresolved: list[dict] | None = None,
    rewrite_failed: bool = False,
    exclude_ids: list[str] | None = None,
) -> dict:
    all_ids = {e["evidence_id"] for e in evidences}
    shown = set(shown_evidence_ids) if shown_evidence_ids is not None else all_ids  # None: 단독 실행(_main) 호환
    import_check = "sandbox" if USE_SANDBOX else ("static" if _target_symbols() is not None else "skipped")
    errors, warnings = [], []

    if rewrite_failed:  # LLM 호출 실패로 원본이 그대로 돌아온 경우: 구버전 메서드만 있는 코드는 아래 검사를 우연히 통과한다
        errors.append(issue("rewrite_failed", "rewriter가 결과를 만들지 못했습니다(LLM 호출 실패). 다시 시도합니다."))
    if import_check == "skipped":
        warnings.append(issue("import_check_skipped", "1.x 심볼 덤프(data/raw/symbols)가 없어 import 존재 검사를 건너뜁니다."))

    # 원본/새 코드는 한 번씩만 파싱해서 아래 검사들이 같이 쓴다
    old_tree = _parse(old_code)
    tree, syntax_errors = check_syntax(new_code)                                         # 1
    used = _names(tree) if tree is not None else None  # None이면 2번이 예외 없이 엄격하게 검사
    errors += syntax_errors
    errors += check_evidence_ids(changes, shown, all_ids, used)                          # 2
    errors += check_changes(old_code, new_code, changes)                                 # 3

    if tree is not None:  # 문법이 맞을 때만 코드 분석 가능
        imports = collect_imports(tree)
        old_paths = {p for p, _, _ in collect_imports(old_tree)} if old_tree is not None else set()
        ev_paths = evidence_import_paths(evidences, shown)
        parent = {c: p for p in ast.walk(tree) for c in ast.iter_child_nodes(p)}       # 8·10·11 공통

        e4, w4, handled = check_legacy_imports(imports, set(exclude_ids or []))          # 4
        e5, w5 = check_import_exists(imports, handled, evidences, shown,
                                     {loose_key(p) for p, _ in ev_paths}, old_paths)       # 5
        w6 = check_legacy_methods(new_code)                                              # 6 (경고만)
        e7, w7 = check_unused_imports(tree, used, _names(old_tree))                      # 7
        e8 = check_return_type(old_code, old_tree, tree, parent)                         # 8
        e9, w9 = check_undefined_names(tree, old_tree, ev_paths)                         # 9
        e10 = check_invoke_subscript(tree, parent, _lcel_evidence_id(evidences, shown))  # 10
        e11 = check_chain_io_keys(tree, parent)                                          # 11
        errors += e4 + e5 + e7 + e8 + e9 + e10 + e11
        warnings += w4 + w5 + w6 + w7 + w9

    return {
        "passed": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {"errors": len(errors), "warnings": len(warnings), "changes": len(changes),
                    "unresolved": len(unresolved or []), "import_check": import_check},
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
        exclude_ids=state.get("exclude_ids", []),
    )
    return {
        "verify_result": result,
        "attempt": state.get("attempt", 0) + 1,
        "exclude_ids": faulty_evidence_ids(result["errors"]),  # reducer(merge_ids)가 중복 없이 누적한다
    }


def route_after_verify(state: MigrationState) -> str:
    """'done' 통과 또는 최대 시도 / 'retry' 근거 문제가 있어 retriever부터 / 'rewrite' 근거와 상관없는 오류만 있어 rewriter로.
    migration.py · supervisor.py:
        builder.add_conditional_edges("verifier", route_after_verify,
                                      {"retry": "retriever", "rewrite": "rewriter", "done": END})"""
    result = state["verify_result"]
    if result["passed"] or state.get("attempt", 0) >= MAX_ATTEMPTS:
        return "done"
    return "retry" if any(e["type"] in NEEDS_RETRIEVAL for e in result.get("errors", [])) else "rewrite"


# 단독 실행용 테스트 (OpenAI 키 없이 검사 로직만 확인)

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
    evidences = []
    for path in parse_import_paths(SAMPLE_OLD):
        hit = lookup(path)
        if hit:
            evidences.append({"evidence_id": hit.record["id"], "source": "import_map", "old": path, "new": hit.new,
                              "kind": hit.record["kind"], "import_status": hit.record.get("import_status")})
    eid = {e["old"].rsplit(".", 1)[-1]: e["evidence_id"] for e in evidences}  # 클래스 이름 → 근거 ID
    change = lambda ln, old, new, cls: {"old_line": ln, "old": old, "new": new, "evidence_ids": [eid.get(cls, "?")]}
    changes = [
        change(1, "from langchain.chat_models import ChatOpenAI", "from langchain_openai import ChatOpenAI", "ChatOpenAI"),
        change(2, "from langchain.chains import LLMChain", "", "LLMChain"),
        change(3, "from langchain.prompts import PromptTemplate",
               "from langchain_core.prompts import PromptTemplate\nfrom langchain_core.output_parsers import StrOutputParser",
               "PromptTemplate"),
        change(7, "chain = LLMChain(llm=llm, prompt=prompt)", "chain = prompt | llm | StrOutputParser()", "LLMChain"),
        change(8, 'print(chain.run(product="양말"))', 'print(chain.invoke({"product": "양말"}))', "LLMChain"),
    ]
    print(json.dumps(verify(SAMPLE_OLD, SAMPLE_NEW, changes, evidences), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    _main()