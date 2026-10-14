from functools import lru_cache
from src.graph.state import MigrationState
from src.rag.retrieval.hybrid import RetrievalEngine

@lru_cache(maxsize=1)
def get_retriever_engine() -> RetrievalEngine:
    return RetrievalEngine()

def retriever_node(state: MigrationState) -> dict:
    query = state.get("old_code") or state["question"]
    evidences = get_retriever_engine().retrieve(
        query,
        attempt=state.get("attempt", 0),
        exclude_ids=state.get("exclude_ids", []),
    )

    return {"evidences": [e.to_dict() for e in evidences]}