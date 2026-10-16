# check_nodes.py: 노드 4개를 재시도 없이 한 번씩 실행해 어느 노드에서 문제가 생기는지 확인하는 디버깅용 스크립트 (OpenAI API 호출 있음)
# 실행 python check_nodes.py

import importlib
import json
import os
import sys
import traceback

from dotenv import load_dotenv

QUESTION = '''아래 코드를 LangChain 1.x 버전으로 바꿔줘.

```python
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

llm = ChatOpenAI(temperature=0)
prompt = PromptTemplate.from_template("{product}을 만드는 회사 이름을 지어줘")
chain = LLMChain(llm=llm, prompt=prompt)
print(chain.run(product="양말"))
```'''

# (화면에 보일 이름, 모듈 경로, 함수 이름)
STEPS = [
    ("analyzer", "src.graph.nodes.analyzer_node", "analyzer_node"),
    ("retriever", "src.graph.nodes.retriever_node", "retriever_node"),
    ("rewriter", "src.graph.nodes.rewriter_node", "rewriter_node"),
    ("verifier", "src.graph.nodes.verifier_node", "verifier_node"),
]


def stop(msg: str) -> None:
    traceback.print_exc()
    print(f"\n[중단] {msg}")
    print("       위 Traceback의 '마지막 줄'이 실제 에러 원인입니다.")
    sys.exit(1)


def show(name: str, out: dict) -> None:
    """노드 결과에서 확인해야 할 것만 출력한다."""
    if name == "analyzer":
        print("[old_code]\n" + (out.get("old_code") or "(비어 있음)"))
        print("\n[analysis]\n" + json.dumps(out.get("analysis"), ensure_ascii=False, indent=2)[:1500])

    elif name == "retriever":
        evs = out.get("evidences") or []
        print(f"근거 {len(evs)}개")
        for e in evs:
            print(f"  - {e.get('evidence_id')}  [{e.get('source')}]  {e.get('old') or ''} -> {e.get('new') or ''}")
        if not evs:
            print("  근거가 0개입니다. data/vectordb, data/processed가 로컬에 있는지 확인하세요.")

    elif name == "rewriter":
        if out.get("rewrite_failed"):
            print("LLM 호출 실패 → 원본 코드를 그대로 반환했습니다")
            print(out.get("unresolved"))
            return
        print("[new_code]\n" + (out.get("new_code") or ""))
        print("\n[changes]")
        for c in out.get("changes") or []:
            print(f"  L{c.get('old_line')}: {c.get('old')!r} -> {c.get('new')!r}  {c.get('evidence_ids')}")
        print("[unresolved]", out.get("unresolved") or "없음")

    elif name == "verifier":
        r = out.get("verify_result") or {}
        print(f"passed = {r.get('passed')}   (import 검사 방식: {(r.get('summary') or {}).get('import_check')})")
        for e in r.get("errors") or []:
            print(f"  ERROR [{e['type']}] {e['message']}")
        for w in r.get("warnings") or []:
            print(f"  warn  [{w['type']}] {w.get('path') or ''} {w['message']}")


def main() -> None:
    load_dotenv()
    if not os.getenv("OPENAI_API_KEY"):
        print("[중단] OPENAI_API_KEY가 없습니다. 프로젝트 루트의 .env 파일을 확인하세요.")
        sys.exit(1)

    state: dict = {"question": QUESTION}

    for name, module_path, func_name in STEPS:
        print(f"\n{'=' * 15} {name} {'=' * 15}")

        # 1. import 확인: 파일 경로·패키지·import 문 오류가 여기서 걸린다
        try:
            node = getattr(importlib.import_module(module_path), func_name)
        except Exception:
            stop(f"{name} 노드를 import하지 못했습니다 ({module_path}).")

        # 2. 실행 확인: 노드 내부 로직 오류가 여기서 걸린다
        try:
            out = node(state) or {}
        except Exception:
            stop(f"{name} 노드 실행 중 에러가 났습니다.")

        # 3. 결과를 state에 합친다 (LangGraph가 노드 사이에서 하는 일을 흉내)
        state.update(out)
        show(name, out)

    print("\n[완료] 네 노드가 모두 에러 없이 실행됐습니다. 이제 python app.py 로 전체 그래프를 돌려 보세요.")


if __name__ == "__main__":
    main()