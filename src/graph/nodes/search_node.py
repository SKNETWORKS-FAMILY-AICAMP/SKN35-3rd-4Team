import json
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from src.graph.state import RootState
from src.prompt.classifier_prompt import classifier_prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

def search_node(state: RootState):
    response = llm.invoke(
        [
            SystemMessage(content=classifier_prompt),
            HumanMessage(content=state["question"]),
        ]
    )

    print(f'classifier_node response :\n{response}')

    result = response.content

    return { 'classification': result }