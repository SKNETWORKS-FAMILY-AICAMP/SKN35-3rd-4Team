import json
from langchain_core.messages import HumanMessage
from src.graph.supervisor import supervisor

def main():
    question = """Document 만들어서 쓰는 부분인데 0.3 코드예요. 1.x로 바꿔 주세요.

```python
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate

docs = [Document(page_content="LangChain 1.0 출시", metadata={"src": "news"})]
prompt = ChatPromptTemplate.from_messages([("system", "요약가"), ("human", "{text}")])
print(prompt.format_messages(text=docs[0].page_content))
```"""

    # supervisor = migration_pipeline()
    # result = supervisor.invoke({ "question": question })

    graph = supervisor()
    result = graph.invoke({ "messages": [HumanMessage(content=question)] })
    print(result)

    print("\n[응답]")
    print(result.get("new_code") or result.get("old_code"))
    print(result.get("analysis") or None)
    print(len(result.get("evidences", [])))

    # 바꾼 줄과 근거 ID, 바꾼 이유 (조건 4)
    print("\n[변경 내역]")
    for c in result.get("changes") or []:
        print(f"  L{c.get('old_line')}: {c.get('old')!r} -> {c.get('new')!r}  {c.get('evidence_ids')}")
        print(f"      이유: {c.get('reason')}")

    # 근거가 부족해 바꾸지 않은 줄
    print("\n[미해결]")
    print(json.dumps(result.get("unresolved", []), ensure_ascii=False, indent=2))

    # 사용자 안내 사항과 설치가 필요한 패키지 (조건 4)
    print("\n[안내]", result.get("rewrite_notes"), "/ 설치:", result.get("install_packages"))

    # 마지막에 검증 결과 출력 추가했음
    print("검증 통과:", (result.get("verify_result") or {}).get("passed"), "/ 시도:", result.get("attempt"))
    print(json.dumps(result.get("verify_result", {}).get("errors", []), ensure_ascii=False, indent=2))
    print(json.dumps(result.get("verify_result", {}).get("warnings", []), ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
