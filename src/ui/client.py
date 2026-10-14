"""화면이 챗봇을 부르는 단 한 곳.

1.x 로 바꾸는 요청은 팀 그래프(src/graph/supervisor.py 의 migration_pipeline)를 부른다.
    analyzer → retriever → rewriter → verifier (실패하면 retriever 로, 최대 3회)
그래프를 쓸 수 없을 때(그래프 코드 · 패키지 · 키가 없음)나 1.x 가 아닌 버전(되돌리기)은
화면 쪽 임시 결과(mock.py)를 쓴다. 결과 모양은 docs/화면_결과_모양.md.
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
        from src.graph.supervisor import migration_pipeline
        _graph = migration_pipeline()
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
    v = state.get("verify_result") or {}
    passed = bool(v.get("passed")) and not state.get("rewrite_failed")
    attempts = state.get("attempt", 0)
    errors = v.get("errors") or []
    message = (f"{attempts}회 만에 검사 통과" if passed else
               f"{attempts}회 시도했지만 검사를 통과하지 못했어요: " +
               "; ".join(e.get("message", "") for e in errors[:3]))
    return {
        "target_version": target_version,
        "original_code": state.get("old_code") or code,
        "migrated_code": state.get("new_code") or state.get("old_code") or code,
        "changes": changes,
        "verification": {"success": passed, "attempts": attempts, "message": message},
        "unresolved": state.get("unresolved") or [],
        "notes": state.get("rewrite_notes") or [],
        "install_packages": state.get("install_packages") or [],
        "warnings": [w.get("message", "") for w in v.get("warnings") or []],
        "mode": "graph",
    }


def run(code: str, target_version: str = TARGET_VERSIONS[0], source_version: str | None = None,
        question: str | None = None) -> dict:
    """옛 코드(와 사용자 요청 글)를 넣으면 결과(dict)를 돌려준다.

    source_version: 사용자가 고른 옛 버전 (None 이면 자동 감지). 결과에 감지 결과도 담는다.
    question: 사용자가 보낸 글 전체 (자연어 요청 + 코드). 그래프에는 이 글을 그대로 넘긴다.
    """
    graph, _ = _pipeline()
    if graph is not None and target_version == "1.x":
        text = question or f"아래 코드를 LangChain 1.x로 바꿔 줘.\n\n```python\n{code}```"
        if source_version:
            text = f"(지금 코드 버전: LangChain {source_version})\n{text}"
        try:
            result = _from_graph(graph.invoke({"question": text}), code, target_version)
        except Exception as e:               # 그래프 실행 중 오류 → 화면은 임시 결과로 계속 동작
            result = run_mock(code, target_version)
            result["note"] = f"팀 그래프 실행 중 오류가 나서 임시 결과를 보여 줘요 ({type(e).__name__}: {str(e)[:150]})"
    else:
        result = run_mock(code, target_version)
        if graph is not None:
            result["note"] = "1.x 가 아닌 버전은 아직 팀 그래프가 지원하지 않아 화면 쪽 임시 결과예요."
    result["source_version"] = source_version
    detector = load("version_detect")          # 선택 기능. 없으면 감지 결과는 비어 있음
    result["detected"] = detector.detect(code) if detector else {"candidates": [], "clues": [], "source": None}
    return result
