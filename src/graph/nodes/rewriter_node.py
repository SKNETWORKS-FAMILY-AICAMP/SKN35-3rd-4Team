"""rewriter 노드: 구버전 코드 + 검색 근거 → 1.x 코드.

흐름
    1. state에서 old_code / evidences / analysis / verify_result(재시도 피드백)를 꺼낸다
    2. 근거를 [근거ID] 블록으로 정리하고, 코드에 줄 번호를 붙여 프롬프트를 만든다
       - 재시도면 이전 시도에서 인용한 근거를 항상 포함한다(pin). 통과했던 줄의 근거가 빠지면 같은 ID를 다시 달 수 없어 검증이 계속 실패하기 때문이다.
    3. LLM을 구조화 출력(RewriteResult)으로 호출한다
       - 필드 누락 같은 일시적 오류는 한 번 재시도하고, 그래도 실패하면 원본 코드를 돌려준다 (노드 하나의 예외로 그래프 전체가 멈추지 않게 하려고)
    4. 후처리(코드펜스·줄 번호 접두어 제거, 변환 후 안 쓰는 import 삭제, 설치 패키지 계산)는 LLM이 아니라 코드로 한다
    5. new_code, changes, unresolved, rewrite_notes, install_packages, shown_evidence_ids, rewrite_failed를 돌려준다

state.py
    evidences: list[dict]           ← retriever가 채운다. 이 키가 state에 없으면 LangGraph가 조용히 버린다
    shown_evidence_ids: list[str]   ← 이 노드가 채운다
    rewrite_failed: bool            ← 이 노드가 채운다. verifier가 읽어 LLM 호출 실패를 오류로 처리한다
"""

import ast
import json
import os
import re
import sys

from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from pydantic import BaseModel, Field

from src.graph.state import MigrationState
from src.prompt.rewriter_prompt import rewriter_system_prompt, rewriter_user_template

load_dotenv()

MODEL_NAME = os.getenv("REWRITER_MODEL", "gpt-4o-mini")
MAX_DOC_CHARS = 1800   # 문서 근거 한 개당 프롬프트에 넣을 최대 글자 수 (토큰 절약)
MAX_DOC_EVIDENCE = 5   # 문서 근거는 점수 상위 몇 개만 넣을지 (pin된 근거 포함 개수)
LLM_RETRIES = 2        # 구조화 출력 실패(필드 누락 등) 시 총 시도 횟수

MAP_SOURCES = ("import_map", "method_map")


# 출력 스키마

class Change(BaseModel):
    old_line: int | None = Field(default=None, description="OLD_CODE 기준 줄 번호. 새로 추가한 줄이면 null")
    old: str = Field(description="바꾸기 전 코드(줄 번호 접두어 없이). 새로 추가한 줄이면 빈 문자열")
    new: str = Field(description="바꾼 뒤 코드(줄 번호 접두어 없이). 지운 줄이면 빈 문자열")
    evidence_ids: list[str] = Field(description="이 변경을 뒷받침하는 근거 ID 목록 (EVIDENCE에 있는 것만)")
    reason: str = Field(description="왜 바꿨는지 한국어 한 문장")


class Unresolved(BaseModel):
    old_line: int | None = Field(default=None, description="OLD_CODE 기준 줄 번호")
    code: str = Field(description="바꾸지 못한 줄의 원문(줄 번호 접두어 없이)")
    reason: str = Field(description="근거가 부족한 이유. 한국어")


class RewriteResult(BaseModel):
    new_code: str = Field(description="변환된 전체 코드. 코드펜스와 줄 번호 접두어 없이")
    changes: list[Change] = Field(default_factory=list, description="바꾼 단위별 기록")
    unresolved: list[Unresolved] = Field(default_factory=list, description="근거 부족으로 바꾸지 못한 줄")
    notes: list[str] = Field(default_factory=list, description="사용자 안내 사항. 한국어")


# LLM (처음 호출할 때 한 번만 생성)

_llm = None

def get_structured_llm():
    """temperature=0: 변환은 창의성이 아니라 재현성이 중요하다.
    function_calling 방식: 중첩 스키마에서 json_schema strict 모드보다 호환성이 좋다.
    대신 strict가 아니라 필수 필드를 빼먹으면 ValidationError가 날 수 있어 with_retry로 한 번 더 시도한다."""
    global _llm
    if _llm is None:
        _llm = (
            ChatOpenAI(model=MODEL_NAME, temperature=0)
            .with_structured_output(RewriteResult, method="function_calling")
            .with_retry(stop_after_attempt=LLM_RETRIES)
        )
    return _llm


def number_lines(code: str) -> str:
    """LLM이 줄 번호를 직접 세지 않도록 코드가 번호를 붙인다."""
    return "\n".join(f"{i}| {line}" for i, line in enumerate(code.splitlines(), start=1))


def _similar_to(e: dict) -> str | None:
    """fuzzy_map 근거의 실제 구 경로. hybrid.py가 e['old']를 사용자 경로로 덮어쓰므로 signals에서 꺼낸다."""
    for s in e.get("signals") or []:
        if s.startswith("similar_to:"):
            return s.split(":", 1)[1]
    return None


def _cut_doc_text(text: str) -> str:
    """긴 문서 근거를 자른다. 코드 블록(```)이 열린 채로 끊기지 않게 한다. 펜스 개수가 홀수면 열린 블록 안에서 잘린 것이다
    → 그 블록 앞에서 자르고(충분히 남을 때), 아니면 그대로 자르고 펜스를 닫아 준다."""
    if len(text) <= MAX_DOC_CHARS:
        return text

    head = text[:MAX_DOC_CHARS]
    fences = [m.start() for m in re.finditer(r"^```", head, re.MULTILINE)]

    if len(fences) % 2 == 1:
        if fences[-1] > MAX_DOC_CHARS // 2:
            head = head[:fences[-1]].rstrip()
            return head + "\n...(생략)"

        return head.rstrip() + "\n```\n...(생략)"

    return head.rstrip() + "\n...(생략)"


def _map_block(e: dict) -> str:
    if e["source"] == "import_map":
        head = (f"[{e['evidence_id']}] import_map ({e.get('match')})\n"
                f"구 경로: {e.get('old')}\n"
                f"1.x 경로: {e.get('new') or '(없음 - unresolved)'}\n"
                f"kind: {e.get('kind')} / import_status: {e.get('import_status')}")
        if e.get("alternative"):
            head += f"\n대안(alternative): {e['alternative']}"
        if "via_module" in (e.get("signals") or []):
            head += "\n(모듈 단위 매핑으로 계산된 경로)"
        if e.get("match") == "fuzzy_map":
            head += (f"\n주의: 정확매칭이 아닙니다. 이 대응표의 실제 구 경로는 '{_similar_to(e) or '?'}'입니다. "
                     f"마지막 이름(클래스/함수명)이 위 '구 경로'와 다르면 쓰지 마세요.")
        return head
    # method_map: hybrid.py에서 new=대체 메서드, alternative=note, signals[0]=호출 형태
    call = (e.get("signals") or [""])[0]
    return (f"[{e['evidence_id']}] method_map\n"
            f"구 호출: {e.get('old')} {call}\n"
            f"대체: {e.get('new')} / 1.x 상태: {e.get('kind')}\n"
            f"Note: {e.get('alternative') or '(없음)'}")


def format_evidence(evidences: list[dict], pinned_ids: set[str] | frozenset[str] = frozenset()) -> tuple[str, list[str]]:
    """근거 dict 목록 → ([근거ID]로 시작하는 텍스트 블록, 실제로 보여준 근거 ID 목록).

    대응표 근거(import_map, method_map)는 전부, 문서 근거는 MAX_DOC_EVIDENCE개만 넣는다.
    대응표가 정확한 사실이고 문서는 사용법 예시라서 우선순위가 다르다.
    pinned_ids(이전 시도에서 인용한 근거)는 점수와 관계없이 먼저 넣는다.
    """
    maps = [e for e in evidences if e.get("source") in MAP_SOURCES]
    docs = [e for e in evidences if e.get("source") not in MAP_SOURCES]

    pinned = [e for e in docs if e["evidence_id"] in pinned_ids]
    rest = sorted((e for e in docs if e["evidence_id"] not in pinned_ids),
                  key=lambda e: -(e.get("score") or 0))
    docs = pinned + rest[:max(0, MAX_DOC_EVIDENCE - len(pinned))]

    blocks = [_map_block(e) for e in maps]
    for e in docs:
        blocks.append(
            f"[{e['evidence_id']}] {e.get('source')} (era {e.get('era')}) "
            f"{e.get('title') or ''} > {e.get('section') or ''}\n{_cut_doc_text(e.get('text') or '')}"
        )

    shown = [e["evidence_id"] for e in maps + docs]
    text = "\n\n---\n\n".join(blocks) if blocks else "(없음)"
    return text, shown


def format_hints(analysis) -> str:
    """analyzer 결과(dict 또는 str)에서 줄·심볼·이유만 뽑는다. evidence는 일부러 뺀다(검증 안 됨)."""
    if not analysis:
        return "(없음)"
    if isinstance(analysis, str):
        try:
            analysis = json.loads(analysis)
        except json.JSONDecodeError:
            return analysis[:1500]
    if not isinstance(analysis, dict):
        return "(없음)"
    findings = analysis.get("findings") or analysis.get("issues") or []
    # analyzer 스키마가 바뀌어도 동작하게 두 키를 모두 본다 (line / line_start, reason / what_changed)
    # new_symbol은 일부러 넣지 않는다: analyzer가 근거 없이 추측한 경로라 틀릴 수 있다
    lines = [
        f"- line {f.get('line') or f.get('line_start')}: {f.get('symbol')} ({f.get('issue_type')}) "
        f"{f.get('reason') or f.get('what_changed') or ''}"
        for f in findings if isinstance(f, dict)
    ]
    return "\n".join(lines) if lines else "(없음)"


def is_retry(verify_result: dict | None) -> bool:
    return bool(verify_result) and not verify_result.get("passed", True)


def format_feedback(verify_result: dict | None, prev_code: str | None, prev_changes: list[dict]) -> str:
    """verifier 실패 결과를 다음 시도에 넘긴다.
    이전 changes도 함께 넘겨야 '지적되지 않은 항목은 유지'(프롬프트 규칙 9)를 LLM이 지킬 수 있다."""
    if not verify_result:
        return "(없음 - 첫 시도)"
    if not is_retry(verify_result):
        return "(없음)"
    errors = json.dumps(verify_result.get("errors", []), ensure_ascii=False, indent=2)
    changes = json.dumps(prev_changes, ensure_ascii=False, indent=2)
    return (f"이전 결과 코드:\n{prev_code or ''}\n\n"
            f"이전 변경 기록 (지적되지 않은 항목은 같은 코드, 같은 evidence_ids로 다시 기록):\n{changes}\n\n"
            f"검증 실패 항목:\n{errors}")


# 후처리

FENCE = re.compile(r"^\s*```[\w-]*\n(.*?)\n```", re.DOTALL) # 시작 펜스만 고정
LINE_NO = re.compile(r"^\d+\| ?")


def strip_fence(code: str) -> str:
    m = FENCE.match(code)
    return m.group(1) if m else code.strip("\n")


def strip_line_numbers(code: str) -> str:
    """LLM이 OLD_CODE의 '3| ' 접두어를 복사한 경우만 제거한다.
    비어 있지 않은 모든 줄에 붙어 있을 때만 지운다 (정상 코드를 잘못 건드리지 않게)."""
    lines = code.splitlines()
    body = [line for line in lines if line.strip()]
    if body and all(LINE_NO.match(line) for line in body):
        return "\n".join(LINE_NO.sub("", line, count=1) for line in lines)
    return code


def clean_code(code: str) -> str:
    return strip_line_numbers(strip_fence(code))


def _remove_line_from(text: str, line: str) -> tuple[str, bool]:
    """여러 줄 문자열에서 line과 같은 줄(앞뒤 공백 무시)을 지운다."""
    lines = text.splitlines()
    kept = [l for l in lines if l.strip() != line]
    return "\n".join(kept), len(kept) != len(lines)


def drop_leftover_imports(old_code: str, new_code: str, changes: list[dict]) -> tuple[str, list[dict], list[str]]:
    """변환하고 남은 import 줄을 지우고 changes에 '삭제'로 기록한다.
    예: LLMChain(...)을 prompt | llm 으로 바꿨는데 from langchain_classic.chains import LLMChain 이 남은 경우.

    LLM이 verifier의 unused_import 피드백을 받아도 이 줄을 반복해서 남기는 일이 있어서(재시도 3회 모두 실패)
    판단이 필요 없는 기계적인 정리는 코드로 한다. 기준은 verifier의 unused_import 오류와 같다:
        - from langchain... / from langgraph... import 문이고, 한 줄짜리
        - 그 줄의 이름을 새 코드에서 하나도 안 쓰고, 원래 코드에서는 모두 쓰던 이름
    반환: (정리된 new_code, 고친 changes, 지운 이름 목록)"""
    try:
        new_tree, old_tree = ast.parse(new_code), ast.parse(old_code)
    except SyntaxError:
        return new_code, changes, []   # 문법 오류는 verifier가 잡게 둔다

    used = {n.id for n in ast.walk(new_tree) if isinstance(n, ast.Name)}
    old_used = {n.id for n in ast.walk(old_tree) if isinstance(n, ast.Name)}
    new_lines = new_code.splitlines()

    # 1. new_code에서 지울 import 줄 찾기
    targets = []   # (줄 번호 0부터, 줄 원문, 이름들)
    for node in ast.walk(new_tree):
        if not (isinstance(node, ast.ImportFrom) and node.module and node.level == 0
                and node.module.startswith(("langchain", "langgraph"))
                and node.lineno == node.end_lineno):
            continue
        names = [a.asname or a.name for a in node.names]
        if "*" in names or any(n in used for n in names) or not all(n in old_used for n in names):
            continue  # 하나라도 쓰거나, 원래부터 안 쓰던 이름이 섞이면 사용자 코드이므로 건드리지 않음
        targets.append((node.lineno - 1, new_lines[node.lineno - 1].strip(), names))
    if not targets:
        return new_code, changes, []

    # 2. 원래 코드의 import 줄: 이름 → (줄 번호, 원문)
    old_lines = old_code.splitlines()
    old_imports = {}
    for node in ast.walk(old_tree):
        if isinstance(node, (ast.Import, ast.ImportFrom)) and node.lineno == node.end_lineno:
            for a in node.names:
                old_imports[a.asname or a.name] = (node.lineno, old_lines[node.lineno - 1].strip())

    # 3. changes 고치기
    changes = [dict(c) for c in changes]
    dropped = []
    for _, line, names in targets:
        dropped += names
        recorded = False
        for c in changes:   # 3-1. 이 줄을 new로 기록한 변경이 있으면 그 줄만 빼서 '삭제'로 바꿈 (근거 ID는 그대로)
            c["new"], hit = _remove_line_from(c.get("new") or "", line)
            if hit:
                c["reason"] = (c.get("reason") or "") + " (변환 후 쓰지 않아 import 삭제)"
                recorded = True
        if recorded:
            continue
        old = old_imports.get(names[0])   # 3-2. 기록이 없으면 원래 코드의 그 import 줄을 삭제한 것으로 기록
        if old and not any(c.get("old_line") == old[0] for c in changes):
            changes.append({"old_line": old[0], "old": old[1], "new": "", "evidence_ids": [],
                            "reason": "변환 후 쓰지 않게 된 import라 삭제했습니다."})

    # 4. new_code에서 줄 삭제
    drop_idx = {i for i, _, _ in targets}
    new_code = "\n".join(l for i, l in enumerate(new_lines) if i not in drop_idx)
    return new_code, changes, dropped


def required_packages(code: str) -> list[str]:
    """new_code의 import에서 pip 패키지명을 계산한다. langchain_openai → langchain-openai.
    LLM에게 맡기지 않는 이유: 패키지명 오타는 설치 실패로 바로 이어진다."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return []
    tops = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            tops.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
            tops.add(node.module.split(".")[0])
    return sorted(t.replace("_", "-") for t in tops if t.startswith(("langchain", "langgraph")))


def _failure_result(old_code: str, shown: list[str], error: Exception) -> dict:
    """LLM 호출이 끝내 실패하면 원본을 그대로 돌려준다.
    verifier는 rewrite_failed=True를 보고 실패 처리 → 재시도 루프나 최대 시도 횟수 처리로 넘어간다.
    (구버전 경로가 남은 것만으로는 못 잡는다. 구버전 메서드만 있는 코드는 원본 그대로여도 검사를 통과하기 때문)"""
    return {
        "new_code": old_code,
        "changes": [],
        "unresolved": [{"old_line": None, "code": "", "reason": f"rewriter 출력 실패: {type(error).__name__}: {str(error)[:200]}"}],
        "rewrite_notes": ["변환 결과를 만들지 못해 원본 코드를 그대로 반환했습니다."],
        "install_packages": required_packages(old_code),
        "shown_evidence_ids": shown,
        "rewrite_failed": True, # verifier가 이 값을 보고 통과시키지 않게 
    }


# rewrite 함수

def rewrite(
    old_code: str,
    evidences: list[dict],
    analysis=None,
    verify_result: dict | None = None,
    prev_code: str | None = None,
    prev_changes: list[dict] | None = None,
    exclude_ids: list[str] | None = None,
    llm=None,
) -> dict:
    llm = llm or get_structured_llm()
    prev_changes = prev_changes or []

    # 1. 이전 시도에서 인용한 근거는 이번 프롬프트에도 보여줌
    # but) verifier가 틀렸다고 제외한 근거(exclude_ids)는 다시 넣지 않음
    pinned = {i for c in prev_changes for i in c.get("evidence_ids", [])} - set(exclude_ids or [])
    evidence_text, shown = format_evidence(evidences, pinned)

    # 2. 프롬프트 조립
    user_msg = rewriter_user_template.format(
        old_code=number_lines(old_code),
        evidence=evidence_text,
        hints=format_hints(analysis),
        feedback=format_feedback(verify_result, prev_code, prev_changes),
    )

    # 3. LLM 호출 (실패해도 그래프를 멈추지 않음)
    try:
        result: RewriteResult = llm.invoke(
            [SystemMessage(content=rewriter_system_prompt), HumanMessage(content=user_msg)]
        )
    except Exception as e:  # ValidationError(필드 누락), OutputParserException, API 오류 등
        print(f"[rewriter] LLM 호출 실패 → 원본을 돌려줍니다: {type(e).__name__}: {e}", file=sys.stderr)
        return _failure_result(old_code, shown, e)

    # 4. 결정적 후처리
    new_code = clean_code(result.new_code)
    changes = []
    for c in result.changes:
        d = c.model_dump()
        d["old"], d["new"] = strip_line_numbers(d["old"]), strip_line_numbers(d["new"])
        changes.append(d)
    unresolved = []
    for u in result.unresolved:
        d = u.model_dump()
        d["code"] = strip_line_numbers(d["code"])
        unresolved.append(d)

    # 변환 잔재 import 정리 (install_packages 계산보다 먼저 해야 langchain-classic 같은 불필요한 패키지가 빠진다)
    notes = list(result.notes)
    new_code, changes, dropped = drop_leftover_imports(old_code, new_code, changes)
    if dropped:
        notes.append(f"변환 후 쓰지 않게 된 import를 삭제했습니다: {', '.join(dropped)}")

    return {
        "new_code": new_code,
        "changes": changes,
        "unresolved": unresolved,
        "rewrite_notes": notes,
        "install_packages": required_packages(new_code),
        "shown_evidence_ids": shown,
        "rewrite_failed": False,
    }


# LangGraph 노드

def rewriter_node(state: MigrationState) -> dict:
    verify_result = state.get("verify_result")
    retrying = is_retry(verify_result)
    return rewrite(
        old_code=state["old_code"],
        evidences=state.get("evidences", []),
        analysis=state.get("analysis"),
        verify_result=verify_result,
        # 재시도일 때만 직전 결과를 넘김 (통과한 결과나 이전 실행의 잔여 값이 섞이지 않게)
        prev_code=state.get("new_code") if retrying else None,
        prev_changes=state.get("changes", []) if retrying else [],
        exclude_ids=state.get("exclude_ids", []),
    )