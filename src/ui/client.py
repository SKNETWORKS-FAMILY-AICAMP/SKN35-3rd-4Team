"""화면이 챗봇을 부르는 단 한 곳.

ask(): 사용자가 보낸 글을 팀 최상위 그래프(src/graph/supervisor.py 의 supervisor)에 그대로 넘긴다.
    질문 분류 → migration (analyzer → retriever → rewriter → verifier, 최대 3회) / search (LangChain 질문) / general
    바꿀 버전은 그래프가 글에서 읽는다 (화면에서 고르지 않음).
run(): 그래프를 쓸 수 없을 때(그래프 코드 · 패키지 · 키가 없음) 화면 쪽 임시 결과(mock.py).
결과 모양은 docs/화면_결과_모양.md.
"""

import os

from .mock import run_mock
from .optional import load
from .versions import ALL_WITH_NEW, LATEST

TARGET_VERSIONS = ALL_WITH_NEW               # 어느 버전으로든 (옛 버전으로 되돌리기 포함)
GRAPH_KEYS = ("OPENAI_API_KEY", "CHROMA_API_KEY", "CHROMA_TENANT", "CHROMA_DATABASE")


def _secrets_to_env(keys) -> None:
    """Streamlit Cloud 의 Secrets 에 적은 값도 환경 변수로 옮긴다 (.env 가 먼저)."""
    try:
        import streamlit as st
        for k in keys:
            if not os.environ.get(k) and k in st.secrets:
                os.environ[k] = str(st.secrets[k])
    except Exception:                                # secrets 파일이 없거나 형식이 틀림
        pass


_graph = None                                        # 성공한 그래프만 기억 (실패는 다음에 다시 시도)
_entry = None                                        # "supervisor" (질문 분류부터) 또는 "migration" (변환만)


def _pipeline():
    """그래프를 한 번만 만든다. 쓸 수 없으면 (None, 이유) — 키를 나중에 넣어도 다시 켜지 않고 연결된다."""
    global _graph
    if _graph is not None:
        return _graph, None
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    if os.environ.get("MIGRATION_NO_GRAPH"):         # 자동 점검용: 그래프 없이 화면만
        return None, "그래프 끔 (MIGRATION_NO_GRAPH)"
    _secrets_to_env(GRAPH_KEYS)
    missing = [k for k in GRAPH_KEYS if not os.environ.get(k)]
    if missing:                                      # 키 확인을 먼저 (그래프 코드는 불러올 때 키가 필요함)
        return None, f".env 또는 Secrets 에 {', '.join(missing)} 없음"
    try:
        global _entry
        try:                                         # 2026-10-15 dev: 최상위 그래프 (질문 분류 → migration / search / general)
            from src.graph.supervisor import supervisor as build
            _entry = "supervisor"
        except ImportError:                          # 그 전 dev: 변환 파이프라인만
            from src.graph.supervisor import migration_pipeline as build
            _entry = "migration"
        _graph = build()
        return _graph, None
    except Exception as e:                           # 그래프 코드나 패키지가 없음
        return None, f"그래프를 불러오지 못함: {type(e).__name__}: {str(e)[:120]}"


def graph_status() -> tuple[bool, str | None]:
    graph, why = _pipeline()
    return graph is not None, why


def mode() -> str:
    """화면 위쪽 배지에 보여 줄 연결 상태."""
    if graph_status()[0]:
        return "graph"
    try:
        import src.rag.retrieval.import_lookup  # noqa: F401  2번 검색기가 있으면 근거는 실제
        return "mock+real_evidence"
    except ImportError:
        return "mock"


def _source_version(analysis, code: str) -> str | None:
    """원래 코드 버전: 챗봇(analyzer)이 읽은 값 → 없으면 코드에 쓰인 기능으로 짐작 (예: "0.1.20 ~ 0.3.30")."""
    if isinstance(analysis, dict):
        v = str(analysis.get("source_version") or "").strip()
        if v and v.lower() not in ("unknown", "none", "latest", "null"):
            return v
    detector = load("version_detect")
    found = detector.detect(code)["candidates"] if detector and code else []
    if not found:
        return None
    return found[0] if len(found) == 1 else f"{found[0]} ~ {found[-1]}"


def _from_graph(state: dict, code: str, target_version: str) -> dict:
    """그래프 State → 화면 결과 모양."""
    evidences = {e.get("evidence_id"): e for e in state.get("evidences") or []}
    changes = []
    for c in state.get("changes") or []:
        ids = c.get("evidence_ids") or []
        ev = next((evidences[i] for i in ids if i in evidences), {})
        changes.append({
            "old": c.get("old") or "(새 줄)", "new": c.get("new") or "(삭제)",
            "kind": ev.get("kind") or ("native" if ids else "unresolved"),
            "evidence_id": ", ".join(ids), "source": ev.get("source"), "alternative": ev.get("alternative"),
            "reason": c.get("reason", ""), "real_evidence": True,
        })
    used = {i for c in state.get("changes") or [] for i in c.get("evidence_ids") or []}
    keep = ("evidence_id", "source", "match", "title", "url", "section", "old", "new", "kind", "alternative",
            "import_status", "text")
    used_evidences = [{k: evidences[i].get(k) for k in keep} for i in sorted(used) if i in evidences]
    v = state.get("verify_result") or {}
    passed = bool(v.get("passed")) and not state.get("rewrite_failed")
    source = _source_version(state.get("analysis"), state.get("old_code") or code)
    attempts = state.get("attempt", 0)
    errors = v.get("errors") or []
    message = (f"{attempts}회 만에 검사 통과" if passed else
               f"{attempts}회 시도했지만 검사를 통과하지 못했어요: " +
               "; ".join(e.get("message", "") for e in errors[:3]))
    return {
        "target_version": target_version,
        "source_version": source,
        "original_code": state.get("old_code") or code,
        "migrated_code": state.get("new_code") or state.get("old_code") or code,
        "changes": changes,
        "evidences": used_evidences,
        "verification": {"success": passed, "attempts": attempts, "message": message},
        "unresolved": state.get("unresolved") or [],
        "notes": state.get("rewrite_notes") or [],
        "install_packages": state.get("install_packages") or [],
        "warnings": [w.get("message", "") for w in v.get("warnings") or []],
        "checks": {"done": bool(v), "errors": [{"type": x.get("type"), "message": x.get("message", "")} for x in errors],
                   "warnings": [{"type": x.get("type"), "message": x.get("message", "")} for x in v.get("warnings") or []]},
        "mode": "graph",
    }


def _last_ai_text(state: dict) -> str:
    for m in reversed(state.get("messages") or []):
        if getattr(m, "type", "") == "ai":
            return m.content if isinstance(m.content, str) else str(m.content)
    return ""


KIND_NAME = {"migration": "코드 변환 요청", "search": "LangChain 질문", "general": "일반 질문"}


ISSUE_NAME = {"import_path_moved": "import 경로 이동", "symbol_renamed": "이름 바뀜", "symbol_removed": "없어짐",
              "api_replaced": "다른 방식으로 대체", "signature_changed": "인자 바뀜", "behavior_changed": "동작 · 반환값 바뀜",
              "deprecated": "폐기 예정", "dependency_split": "패키지 분리", "other": "기타"}
SOURCE_NAME = {"import_map": "import 대응표", "method_map": "메서드 대응표", "latest_docs": "최신 문서",
               "migration_guide": "옛 가이드"}
MAX_DETAIL = 5   # 단계마다 보여 줄 세부 줄 수


def _short(text, n: int = 70) -> str:
    text = " ".join(str(text or "").split())
    return text if len(text) <= n else text[: n - 1] + "…"


def _error_names(errors: list[dict]) -> list[str]:
    """검사 오류 → '검사 이름 ×개수' (결과 패널의 검사 결과 탭과 같은 이름)."""
    from collections import Counter
    from src.ui.result_view import CHECKS
    name_of = {t: name for name, _, types in CHECKS for t in types}
    counts = Counter(name_of.get(e.get("type"), e.get("type") or "기타") for e in errors)
    return [f"{name} ×{c}" if c > 1 else name for name, c in counts.most_common()]


def _step_message(node: str, upd: dict) -> tuple[str, str, list[str]]:
    """끝난 단계 → (끝난 일 한 줄, 다음에 할 일, 세부 내용 줄들). 그래프 노드 이름은 1 · 2 · 3번 그래프 그대로."""
    upd = upd if isinstance(upd, dict) else {}
    if node == "classifier":
        kind = upd.get("classification", "")
        nxt = {"migration": "① 바꿀 부분 찾는 중", "search": "문서에서 답 찾는 중"}.get(kind, "답 쓰는 중")
        why = {"migration": "코드와 바꿔 달라는 요청이 있어 변환 파이프라인으로 보냄",
               "search": "버전 변화를 묻는 질문이라 문서 검색으로 답함",
               "general": "LangChain 버전 변화와 관계없는 질문이라 일반 답변"}.get(kind)
        return f"질문 종류: {KIND_NAME.get(kind, kind)}", nxt, [why] if why else []
    if node == "analyzer":
        a = upd.get("analysis") if isinstance(upd.get("analysis"), dict) else {}
        issues = a.get("issues") or []
        tv = upd.get("target_version")
        details = []
        for i in issues[:MAX_DETAIL]:
            line = i.get("line_start") or i.get("line")
            what = ISSUE_NAME.get(i.get("issue_type"), i.get("issue_type") or "")
            details.append(f"{line}줄 `{_short(i.get('symbol') or i.get('code'), 50)}` · {what}"
                           + (f" — {_short(i.get('what_changed'), 60)}" if i.get("what_changed") else ""))
        if len(issues) > MAX_DETAIL:
            details.append(f"외 {len(issues) - MAX_DETAIL}곳")
        return (f"① 바꿀 부분 {len(issues)}곳 찾음" + (f" · 목표 LangChain {tv}" if tv else ""),
                "② 근거 찾는 중", details)
    if node == "retriever":
        evs = upd.get("evidences") or []
        from collections import Counter
        by_src = Counter(SOURCE_NAME.get(e.get("source"), e.get("source")) for e in evs)
        details = [" · ".join(f"{k} {v}개" for k, v in by_src.items())] if evs else []
        for e in [e for e in evs if e.get("source") == "import_map" and e.get("old")][:3]:
            details.append(f"`{_short(e['old'], 45)}` → `{_short(e.get('new') or '1.x 경로 없음', 45)}`")
        for e in [e for e in evs if e.get("source") in ("latest_docs", "migration_guide")][:2]:
            details.append(f"문서: {_short(e.get('title') or e.get('section') or e.get('evidence_id'), 60)}")
        return f"② 근거 {len(evs)}개 찾음", "③ 코드 고치는 중", details
    if node == "rewriter":
        changes, unresolved = upd.get("changes") or [], upd.get("unresolved") or []
        details = []
        for c in changes[:MAX_DETAIL]:
            old, new = (c.get("old") or "").strip(), (c.get("new") or "").strip()
            where = f"{c['old_line']}줄" if c.get("old_line") else "새 줄"
            if old and new:
                details.append(f"{where}: `{_short(old, 45)}` → `{_short(new, 45)}`")
            elif new:
                details.append(f"{where} 추가: `{_short(new, 60)}`")
            else:
                details.append(f"{where} 삭제: `{_short(old, 60)}`")
        if len(changes) > MAX_DETAIL:
            details.append(f"외 {len(changes) - MAX_DETAIL}곳")
        if unresolved:
            details.append(f"근거가 부족해 그대로 둔 줄 {len(unresolved)}곳")
        return f"③ {len(changes)}곳 고침", "④ 검사하는 중", details
    if node == "verifier":
        v, n = upd.get("verify_result") or {}, upd.get("attempt", 0)
        warns = v.get("warnings") or []
        if v.get("passed"):
            details = ["11가지 검사 모두 통과"] + ([f"참고 경고: {', '.join(_error_names(warns))}"] if warns else [])
            return f"④ 검사 통과 ({n}회차)", "결과 정리하는 중", details
        errors = v.get("errors") or []
        details = [f"걸린 검사: {', '.join(_error_names(errors))}"]
        details += [_short(e.get("message"), 90) for e in errors[:2]]
        if n >= 3:
            return f"④ 검사 {n}회차 실패 ({len(errors)}건) · 최대 3회라 여기서 멈춤", "결과 정리하는 중", details
        return (f"④ 검사 {n}회차 실패 ({len(errors)}건) → 실패 이유를 들고 근거를 다시 찾아요",
                "② 근거 다시 찾는 중", details)
    if node == "search":
        return "문서에서 답을 찾았어요", "정리하는 중", ["찾은 문서 조각만 근거로 답하고, 끝에 출처를 붙여요"]
    if node == "general":
        return "답을 썼어요", "정리하는 중", []
    return f"{node} 완료", "다음 단계 진행 중", []


MIGRATION_NODES = {"analyzer", "retriever", "rewriter", "verifier"}


def ask(text: str, on_step=None, thread_id: str | None = None) -> dict | None:
    """사용자가 보낸 글 하나를 팀 그래프에 그대로 넘긴다. 바꿀 버전도 그래프가 글에서 읽는다.

    on_step(끝난 일, 다음에 할 일, 세부 내용): 단계가 끝날 때마다 불러 화면에 진행 상황을 보여 준다 (그래프의 stream 사용).
    thread_id: 대화(세션) 번호. 그래프에 체크포인터(대화 기억)가 붙으면 이 번호로 대화끼리 섞이지 않게 한다.
    돌려주는 것: {"kind": "migration" | "search" | "general", "reply": 답 글 또는 None, "result": 변환 결과 또는 None,
                 "steps": [{"done", "details", "sec"}] 처리 과정, "seconds": 걸린 시간}
    그래프를 쓸 수 없으면 None (화면이 임시 결과로 처리).
    """
    graph, _ = _pipeline()
    if graph is None:
        return None
    import time
    from langchain_core.messages import HumanMessage
    inputs = {"question": text, "messages": [HumanMessage(content=text)]}
    config = {"configurable": {"thread_id": thread_id}} if thread_id else None
    state, steps, t0 = None, [], time.time()
    turn_kind, ran_migration = None, False                  # 이번 질문에서 실제로 일어난 일 (기억된 옛 상태와 구분)
    for ns, mode, data in graph.stream(inputs, config=config, stream_mode=["updates", "values"], subgraphs=True):
        if mode == "values" and not ns:                     # 최상위 그래프의 지금 상태 (마지막 것이 최종)
            state = data
        elif mode == "updates":
            for node, upd in data.items():
                if node == "migration":                      # 하위 그래프 전체가 끝난 알림은 건너뜀
                    continue
                if node == "classifier" and isinstance(upd, dict):
                    turn_kind = upd.get("classification")
                ran_migration = ran_migration or node in MIGRATION_NODES
                done, nxt, details = _step_message(node, upd)
                steps.append({"done": done, "details": details, "sec": round(time.time() - t0, 1)})
                if on_step:
                    on_step(done, nxt, details)
    if state is None:
        raise RuntimeError("그래프가 결과를 돌려주지 않았어요")
    seconds = round(time.time() - t0, 1)
    # 답의 종류는 '이번 질문'의 분류로 정한다. 그래프가 대화를 기억하면(체크포인터) 앞 질문의
    # verify_result · old_code 가 state에 남아 있어, 인사에도 이전 변환 결과를 보여 주는 문제가 있었다 (10-15)
    kind = turn_kind or state.get("classification") or ("migration" if _entry == "migration" else "general")
    if kind == "migration" or (turn_kind is None and ran_migration):
        target = state.get("target_version") or LATEST["langchain"]
        result = _from_graph(state, state.get("old_code", ""), target)
        result["steps"], result["seconds"] = steps, seconds
        return {"kind": "migration", "reply": None, "result": result, "steps": steps, "seconds": seconds}
    return {"kind": kind, "reply": _last_ai_text(state) or "답을 만들지 못했어요. 다시 물어봐 주세요.", "result": None,
            "steps": steps, "seconds": seconds}


def run(code: str, target_version: str = "1.x", source_version: str | None = None) -> dict:
    """그래프를 쓸 수 없을 때의 화면 쪽 임시 결과 (2번 대응표 근거, 가짜 변환)."""
    result = run_mock(code, target_version)
    result["source_version"] = source_version
    detector = load("version_detect")          # 선택 기능. 없으면 감지 결과는 비어 있음
    result["detected"] = detector.detect(code) if detector else {"candidates": [], "clues": [], "source": None}
    return result
