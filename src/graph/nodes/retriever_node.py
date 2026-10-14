from functools import lru_cache

from src.graph.state import MigrationState
from src.rag.retrieval import DOC_SOURCES
from src.rag.retrieval.hybrid import RetrievalEngine
from src.rag.retrieval.import_lookup import parse_import_paths

MAP_SOURCES = ("import_map", "method_map")
FINDING_DOC_K = 2  # 대응표에 없는 finding 하나당 추가로 찾을 문서 근거 수


@lru_cache(maxsize=1)
def get_retriever_engine() -> RetrievalEngine:
    return RetrievalEngine()


def get_findings(analysis) -> list[dict]:
    if not isinstance(analysis, dict):
        return []
    items = analysis.get("findings") or analysis.get("issues") or []
    return [
        f for f in items
        if isinstance(f, dict) and (f.get("code") or f.get("symbol"))
    ]


def finding_names(finding: dict) -> set[str]:
    names = {p.rsplit(".", 1)[-1] for p in parse_import_paths(finding.get("code") or "")}
    names |= {part for part in (finding.get("symbol") or "").split(".") if part}
    return names


def links_to(evidence: dict, finding: dict) -> bool:
    name = (evidence.get("old") or "").rsplit(".", 1)[-1]
    if not name:
        return False
    if evidence["source"] == "method_map":
        return name in finding_names(finding) or f".{name}(" in (finding.get("code") or "")
    return name in finding_names(finding)


def retriever_node(state: MigrationState) -> dict:
    query = (state.get("old_code") or "").strip() or state["question"]
    attempt = state.get("attempt", 0)
    exclude_ids = set(state.get("exclude_ids") or [])
    target = state.get("target_version")  # 없으면 엔진이 최신으로 처리
    engine = get_retriever_engine()

    evidences = {
        e.evidence_id: {**e.to_dict(), "finding_ids": []}
        for e in engine.retrieve(query, attempt=attempt, exclude_ids=exclude_ids, target_version=target)
    }

    for idx, finding in enumerate(get_findings(state.get("analysis")), start=1):
        finding_id = finding.get("id", idx)
        linked = False
        for ev in evidences.values():
            if ev["source"] in MAP_SOURCES and links_to(ev, finding):
                ev["finding_ids"].append(finding_id)
                linked = True
        if linked:
            continue

        finding_query = "\n".join(filter(None, [finding.get("code"), finding.get("symbol")]))
        for e in engine.retrieve(finding_query, k=FINDING_DOC_K, attempt=attempt, exclude_ids=exclude_ids,
                                 target_version=target):
            if e.source not in DOC_SOURCES:
                continue
            ev = evidences.setdefault(e.evidence_id, {**e.to_dict(), "finding_ids": []})
            ev["finding_ids"].append(finding_id)

    return {"evidences": list(evidences.values())}