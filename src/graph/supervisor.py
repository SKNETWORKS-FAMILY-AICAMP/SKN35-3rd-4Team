from src.graph.state import MigrateState
from langgraph.graph import StateGraph, START, END

builder = StateGraph(MigrateState)

builder_app = builder.compile()