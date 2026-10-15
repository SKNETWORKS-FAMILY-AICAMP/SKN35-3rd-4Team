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


def _step_message(node: str, upd: dict) -> tuple[str, str]:
    """끝난 단계 → (끝난 일 한 줄, 다음에 할 일). 그래프 노드 이름은 1 · 2 · 3번 그래프 그대로."""
    upd = upd if isinstance(upd, dict) else {}
    if node == "classifier":
        kind = upd.get("classification", "")
        nxt = {"migration": "① 바꿀 부분 찾는 중", "search": "문서에서 답 찾는 중"}.get(kind, "답 쓰는 중")
        return f"질문 종류: {KIND_NAME.get(kind, kind)}", nxt
    if node == "analyzer":
        a = upd.get("analysis") if isinstance(upd.get("analysis"), dict) else {}
        n = len(a.get("issues") or [])
        tv = upd.get("target_version")
        return f"① 바꿀 부분 {n}곳 찾음" + (f" · 목표 LangChain {tv}" if tv else ""), "② 근거 찾는 중"
    if node == "retriever":
        return f"② 근거 {len(upd.get('evidences') or [])}개 찾음", "③ 코드 고치는 중"
    if node == "rewriter":
        return f"③ {len(upd.get('changes') or [])}곳 고침", "④ 검사하는 중"
    if node == "verifier":
        v, n = upd.get("verify_result") or {}, upd.get("attempt", 0)
        if v.get("passed"):
            return f"④ 검사 통과 ({n}회차)", "결과 정리하는 중"
        return f"④ 검사 {n}회차 실패 ({len(v.get('errors') or [])}건) → 근거를 다시 찾아 고쳐요", "② 근거 다시 찾는 중"
    if node == "search":
        return "문서에서 답을 찾았어요", "정리하는 중"
    if node == "general":
        return "답을 썼어요", "정리하는 중"
    return f"{node} 완료", "다음 단계 진행 중"


def ask(text: str, on_step=None) -> dict | None:
    """사용자가 보낸 글 하나를 팀 그래프에 그대로 넘긴다. 바꿀 버전도 그래프가 글에서 읽는다.

    on_step(끝난 일, 다음에 할 일): 단계가 끝날 때마다 불러 화면에 진행 상황을 보여 준다 (그래프의 stream 사용).
    돌려주는 것: {"kind": "migration" | "search" | "general", "reply": 답 글 또는 None, "result": 변환 결과 또는 None}
    그래프를 쓸 수 없으면 None (화면이 임시 결과로 처리).
    """
    graph, _ = _pipeline()
    if graph is None:
        return None
    from langchain_core.messages import HumanMessage
    inputs = {"question": text, "messages": [HumanMessage(content=text)]}
    state = None
    for ns, mode, data in graph.stream(inputs, stream_mode=["updates", "values"], subgraphs=True):
        if mode == "values" and not ns:                     # 최상위 그래프의 지금 상태 (마지막 것이 최종)
            state = data
        elif mode == "updates" and on_step:
            for node, upd in data.items():
                if node == "migration":                      # 하위 그래프 전체가 끝난 알림은 건너뜀
                    continue
                on_step(*_step_message(node, upd))
    if state is None:
        raise RuntimeError("그래프가 결과를 돌려주지 않았어요")
    kind = state.get("classification") or ("migration" if _entry == "migration" else "general")
    if kind == "migration" or state.get("verify_result") is not None:
        target = state.get("target_version") or LATEST["langchain"]
        return {"kind": "migration", "reply": None, "result": _from_graph(state, state.get("old_code", ""), target)}
    return {"kind": kind, "reply": _last_ai_text(state) or "답을 만들지 못했어요. 다시 물어봐 주세요.", "result": None}


def run(code: str, target_version: str = "1.x", source_version: str | None = None) -> dict:
    """그래프를 쓸 수 없을 때의 화면 쪽 임시 결과 (2번 대응표 근거, 가짜 변환)."""
    result = run_mock(code, target_version)
    result["source_version"] = source_version
    detector = load("version_detect")          # 선택 기능. 없으면 감지 결과는 비어 있음
    result["detected"] = detector.detect(code) if detector else {"candidates": [], "clues": [], "source": None}
    return result
