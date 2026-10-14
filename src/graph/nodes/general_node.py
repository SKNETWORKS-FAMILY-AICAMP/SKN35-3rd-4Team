from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_openai import ChatOpenAI
from src.graph.state import RootState
from src.prompt.general_prompt import general_prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

def general_node(state: RootState):
    response = llm.invoke(
        [
            SystemMessage(content=general_prompt),
            HumanMessage(content=state["messages"][-1].content),
        ]
    )

    print(f'general_node response :\n{response}')

    return { 'messages': AIMessage(content=response.content) }