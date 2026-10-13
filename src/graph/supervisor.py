from src.graph.state import MigrationState
from langgraph.graph import StateGraph, START, END
from src.graph.nodes.analyzer_node import analyzer_node

def migration_pipeline():
    builder = StateGraph(MigrationState)
    builder.add_node('analyzer', analyzer_node)

    builder.add_edge(START, 'analyzer')
    builder.add_edge('analyzer', END)

    app = builder.compile()

    return app