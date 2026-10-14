from langgraph.graph import END, START, StateGraph

from src.graph.nodes.analyzer_node import analyzer_node
from src.graph.nodes.retriever_node import retriever_node
from src.graph.nodes.rewriter_node import rewriter_node
from src.graph.nodes.verifier_node import route_after_verify, verifier_node
from src.graph.state import MigrationState

def migration():
    builder = StateGraph(MigrationState)

    builder.add_node("analyzer", analyzer_node)
    builder.add_node("retriever", retriever_node)
    builder.add_node("rewriter", rewriter_node)
    builder.add_node("verifier", verifier_node)

    builder.add_edge(START, "analyzer")
    builder.add_edge("analyzer", "retriever")
    builder.add_edge("retriever", "rewriter")
    builder.add_edge("rewriter", "verifier")

    # 검증 결과에 따른 분기: 실패면 retriever로 되돌아가 근거를 다시 찾기 
    builder.add_conditional_edges(
        "verifier",
        route_after_verify,
        {"retry": "retriever", "done": END},
    )

    app = builder.compile()
    
    return app