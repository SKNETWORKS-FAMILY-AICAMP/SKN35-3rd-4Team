from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from src.graph.state import MigrationState
from src.prompt.classifier_prompt import classifier_prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

def classifier_node(state: MigrationState):
    response = llm.invoke(
        [
            SystemMessage(content=classifier_prompt),
            HumanMessage(content=state["messages"][-1].content),
        ]
    )

    result = response.content
    question = ''

    if result != 'general':
        for m in reversed(state["messages"]):
            if m.type == "human":
                question = m.content if isinstance(m.content, str) else str(m.content)

    print(f'classifier_node response : {result}')

    return { 'classification': result, 'question': question }