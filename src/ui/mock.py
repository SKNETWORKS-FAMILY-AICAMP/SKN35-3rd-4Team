"""가짜 변환 결과 (데모용).

1번 그래프와 3번 변환 · 검증이 나오기 전에 화면을 미리 돌려 보기 위한 결과를 만든다.
근거는 2번 검색기(src/rag/retrieval/import_lookup.py)가 있으면 실제 대응표에서 찾고,
없으면 아래 작은 예시표를 쓴다. 코드 변환은 흉내만 낸다 (진짜 변환은 3번 몫).
"""

import re
import zlib

# 2번 대응표가 없을 때 쓰는 작은 예시표 (2번 대응표의 한 줄 모양을 그대로 따름)
SAMPLE_MAP = {
    "langchain.chat_models.ChatOpenAI": ("langchain_openai.ChatOpenAI", "native", None),
    "langchain.llms.OpenAI": ("langchain_openai.OpenAI", "native", None),
    "langchain.embeddings.OpenAIEmbeddings": ("langchain_openai.OpenAIEmbeddings", "native", None),
    "langchain.prompts.PromptTemplate": ("langchain_core.prompts.PromptTemplate", "native", None),
    "langchain.prompts.ChatPromptTemplate": ("langchain_core.prompts.ChatPromptTemplate", "native", None),
    "langchain.schema.Document": ("langchain_core.documents.Document", "native", None),
    "langchain.text_splitter.RecursiveCharacterTextSplitter":
        ("langchain_text_splitters.RecursiveCharacterTextSplitter", "native", None),
    "langchain.vectorstores.FAISS": ("langchain_community.vectorstores.FAISS", "native", None),
    "langchain.chains.LLMChain": ("langchain_classic.chains.LLMChain", "classic_fallback", "RunnableSequence, e.g., `prompt | llm`"),
    "langchain.memory.ConversationBufferMemory":
        ("langchain_classic.memory.ConversationBufferMemory", "classic_fallback", "langchain.agents.create_agent"),
    "langchain.agents.initialize_agent": ("langchain_classic.agents.initialize_agent", "classic_fallback", "langchain.agents.create_agent"),
    "langchain.agents.create_tool_calling_agent":
        ("langchain_classic.agents.create_tool_calling_agent", "classic_fallback", None),
    "langchain.LLMBashChain": (None, "unresolved", None),
}

FROM_IMPORT = re.compile(r"^\s*from\s+([\w.]+)\s+import\s+(.+)$")


def import_paths(code: str) -> list[tuple[str, str]]:
    """(옛 import 줄, 점 경로) 목록. 예: from langchain.prompts import PromptTemplate → langchain.prompts.PromptTemplate"""
    out = []
    for line in code.splitlines():
        m = FROM_IMPORT.match(line)
        if not m or not m.group(1).startswith("langchain"):
            continue
        for name in m.group(2).strip("() ").split(","):
            name = name.split(" as ")[0].strip()
            if name:
                out.append((line.strip(), f"{m.group(1)}.{name}"))
    return out


def find_evidence(path: str) -> dict | None:
    """대응표에서 옛 경로를 찾는다. 2번 검색기가 있으면 실제 대응표, 없으면 예시표."""
    try:
        from src.rag.retrieval.import_lookup import lookup  # 팀 저장소에 2번 코드가 있을 때
        hit = lookup(path)
        if hit is None:
            return None
        rec = hit.record
        return {"old": path, "new": hit.new, "kind": rec["kind"], "evidence_id": rec["id"],
                "source": "import_map", "alternative": rec.get("alternative"), "real": True}
    except ImportError:
        pass
    if path not in SAMPLE_MAP:
        return None
    new, kind, alt = SAMPLE_MAP[path]
    return {"old": path, "new": new, "kind": kind, "evidence_id": f"sample-{zlib.crc32(path.encode()):08x}",
            "source": "import_map", "alternative": alt, "real": False}


def new_import_line(new_path: str) -> str:
    module, name = new_path.rsplit(".", 1)
    return f"from {module} import {name}"


def replacement_line(ev: dict) -> str | None:
    """이 근거로 바꾼 새 줄. LLMChain처럼 대안이 prompt | llm 이면 LCEL로 바꾼다."""
    if ev["kind"] == "classic_fallback" and ev.get("alternative") and "prompt | llm" in ev["alternative"]:
        return "from langchain_core.output_parsers import StrOutputParser"
    return new_import_line(ev["new"]) if ev.get("new") else None


def fake_rewrite(code: str, evidences: list[dict]) -> str:
    """import 줄을 새 위치로 바꾸고, LLMChain 같은 대표 패턴만 흉내 낸다."""
    lines = []
    done = set()
    by_line: dict[str, list[dict]] = {}
    for ev in evidences:
        by_line.setdefault(ev["line"], []).append(ev)
    for line in code.splitlines():
        evs = by_line.get(line.strip())
        if not evs:
            lines.append(line)
            continue
        for ev in evs:
            new = replacement_line(ev) or line
            if new not in done:
                lines.append(new)
                done.add(new)
    out = "\n".join(lines)
    out = re.sub(r"LLMChain\(\s*llm\s*=\s*(\w+)\s*,\s*prompt\s*=\s*(\w+)\s*\)", r"\2 | \1 | StrOutputParser()", out)
    out = re.sub(r"\.run\(\s*(\w+)\s*=\s*([^)]*)\)", r'.invoke({"\1": \2})', out)
    out = re.sub(r"\.run\(", ".invoke(", out)
    return out


def run_mock(code: str, target_version: str) -> dict:
    """화면이 기대하는 결과 모양 (docs/화면_결과_모양.md)."""
    evidences = []
    paths = import_paths(code)
    for line, path in paths:
        ev = find_evidence(path)
        if ev:
            ev["line"] = line
            evidences.append(ev)
    if not evidences:
        message = ("LangChain import 줄을 찾지 못했습니다. 옛 LangChain 코드를 넣어 주세요." if not paths else
                   f"LangChain import {len(paths)}줄을 찾았지만 대응표에서 근거를 찾지 못했어요. "
                   "(지금은 예시 대응표라 일부만 있어요. 팀 저장소에서는 2번 대응표 전체를 씁니다.)")
        return {"target_version": target_version, "original_code": code, "migrated_code": code,
                "changes": [], "steps": _steps(len(paths), ok=False),
                "verification": {"success": False, "attempts": 0, "message": message}, "mode": "mock"}
    migrated = fake_rewrite(code, evidences)
    changes = [{"old": ev["line"], "new": replacement_line(ev) or "-",
                "kind": ev["kind"], "evidence_id": ev["evidence_id"], "source": ev["source"],
                "alternative": ev.get("alternative"), "real_evidence": ev["real"]} for ev in evidences]
    has_classic = any(c["kind"] == "classic_fallback" for c in changes)
    attempts = 2 if has_classic else 1
    return {"target_version": target_version, "original_code": code, "migrated_code": migrated,
            "changes": changes, "steps": _steps(len(evidences), ok=True, retry=has_classic),
            "verification": {"success": True, "attempts": attempts,
                             "message": f"{attempts}회 만에 통과 (가짜 결과)"},
            "mode": "mock+real_evidence" if any(c["real_evidence"] for c in changes) else "mock"}


def _steps(n: int, ok: bool, retry: bool = False) -> list[dict]:
    steps = [{"name": "① analyzer", "detail": f"import 경로 {n}개 찾음"},
             {"name": "② retriever", "detail": "대응표 · 문서에서 근거 찾기"},
             {"name": "③ rewriter", "detail": "근거를 보고 코드 다시 쓰기"}]
    if retry:
        steps += [{"name": "④ verifier", "detail": "1회차: 옛 방식(classic) 사용 → 다시 찾기"},
                  {"name": "② retriever", "detail": "대안 문서 더 찾기"},
                  {"name": "③ rewriter", "detail": "최신 방식으로 다시 쓰기"}]
    steps += [{"name": "④ verifier", "detail": "실행해서 확인 → 통과" if ok else "확인할 코드 없음"},
              {"name": "⑤ report", "detail": "결과 정리"}]
    return steps
