from src.graph.state import MigrationState
from langgraph.graph import StateGraph, START, END
from src.graph.nodes.classifier_node import classifier_node
from src.graph.nodes.general_node import general_node
from src.graph.nodes.search_node import search_node
from src.graph.migration import migration

def prompt_classification(state: MigrationState):
    return state["classification"]

def supervisor():
    builder = StateGraph(MigrationState)

    builder.add_node('classifier', classifier_node)
    builder.add_node('migration', migration()) 
    builder.add_node('search', search_node)
    builder.add_node('general', general_node)
    
    builder.add_edge(START, 'classifier')
    builder.add_conditional_edges(
        'classifier',
        prompt_classification,
        {
            'migration': 'migration',
            'search': 'search',
            'general': 'general'
        }
    )
    builder.add_edge('migration', END)
    builder.add_edge('search', END)
    builder.add_edge('general', END)

    app = builder.compile()

    return app