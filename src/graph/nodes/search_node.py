from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from src.graph.nodes.retriever_node import get_retriever_engine
from src.graph.nodes.rewriter_node import _cut_doc_text
from src.graph.state import MigrationState
from src.prompt.search_prompt import search_prompt, search_user_template

load_dotenv()

SEARCH_K = 6
llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

def format_context(evidences: list[dict]) -> str:
    """근거 목록 → 프롬프트 CONTEXT 블록. 머리글은 "[번호 | source | version]" 형식."""
    if not evidences:
        return "(no results)"

    blocks = []
    for i, e in enumerate(evidences, start=1):
        head = f"[{i} | {e.get('source')} | {e.get('era') or 'unknown'}]"
        location = " > ".join(filter(None, [e.get("title"), e.get("section")]))
        if location:
            head += f" {location}"
        blocks.append(f"{head}\n{_cut_doc_text(e.get('text') or '')}")

    return "\n\n---\n\n".join(blocks)


def search_node(state: MigrationState):
    question = state["messages"][-1].content.strip()
    print(question)
    evidences = [e.to_dict() for e in get_retriever_engine().retrieve(question, k=SEARCH_K)]
    print(f'search_node evidences : {[e["evidence_id"] for e in evidences]}')

    response = llm.invoke(
        [
            SystemMessage(content=search_prompt),
            HumanMessage(content=search_user_template.format(
                context=format_context(evidences),
                question=question,
            )),
        ]
    )

    print(f'search_node response :\n{response}')

    return { 'messages': AIMessage(content=response.content) }

# if __name__ == "__main__":
#     import sys
#     from langchain_core.messages import HumanMessage

#     question = " ".join(sys.argv[1:]) or "랭체인이랑 랭그래프 차이가 뭐야?"
#     result = search_node({"messages": [HumanMessage(content=question)], "classification": "langchain"})
#     print("\n===== answer =====")
#     print(result["messages"].content)