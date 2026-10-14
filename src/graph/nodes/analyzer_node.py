import json
import re
import sys
 
from dotenv import load_dotenv
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_openai import ChatOpenAI
from src.graph.state import MigrationState
from src.prompt.analyzer_prompt import analyzer_prompt
 
load_dotenv()

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

# 질문 안의 ```python ... ``` 코드 블록
CODE_BLOCK = re.compile(r"```(?:python|py)?[ \t]*\n(.*?)```", re.DOTALL)
# LLM 응답 전체를 감싼 ```json ... ``` 코드펜스
JSON_FENCE = re.compile(r"^\s*```(?:json)?[ \t]*\n(.*?)\n?```\s*$", re.DOTALL)


def parse_json(text: str) -> dict:
    m = JSON_FENCE.match(text)
    data = json.loads(m.group(1) if m else text)
    return data if isinstance(data, dict) else {}
 
def fallback_code(question: str) -> str:
    m = CODE_BLOCK.search(question)
    return (m.group(1) if m else question).strip()

# LLM이 old_code를 ```python ... ``` 으로 감싸서 돌려준 경우 펜스를 벗기는 거 
def strip_code_fence(code: str) -> str:
    code = code.strip()
    if code.startswith("```"):
        m = CODE_BLOCK.search(code)
        if m:
            return m.group(1).strip("\n")
    return code

def analyzer_node(state: MigrationState):
    question = state["question"]

    response = llm.invoke(
        [
            SystemMessage(content=analyzer_prompt),
            HumanMessage(content=state["question"]),
        ]
    )

    print(f'analyzer_node response :\n{response.content}')

    try:
        result = parse_json(response.content)
    except json.JSONDecodeError:
        print("[analyzer] JSON 파싱 실패 → 질문의 코드 블록을 그대로 사용합니다", file=sys.stderr)
        print(f"[analyzer] LLM 원문(앞 300자): {response.content[:300]!r}", file=sys.stderr)
        result = {}
 
    old_code = strip_code_fence(result.get("old_code") or "") or fallback_code(question)
    analysis = result.get("analysis") or {}

    return { 'old_code': old_code, 'analysis': analysis }