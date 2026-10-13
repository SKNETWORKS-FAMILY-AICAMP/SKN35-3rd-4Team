import json
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from src.graph.state import MigrationState
from src.prompt.analyzer_prompt import analyzer_prompt

load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

def analyzer_node(state: MigrationState):
    llm = ChatOpenAI(model="gpt-4o-mini", temperature=0.7)

    response = llm.invoke(
        [
            SystemMessage(content=analyzer_prompt),
            HumanMessage(content=state["question"]),
        ]
    )

    print(f'analyzer_node response :\n{response}')

    result = json.loads(response.content)
    old_code = result['old_code']
    analysis = result['analysis']

    return { 'old_code': old_code, 'analysis': analysis }