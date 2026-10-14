import json
from langchain_core.messages import HumanMessage
# from src.graph.supervisor import migration_pipeline
from src.graph.graph import supervisor

def main():
    question = """야 내가 지금 온라인 쇼핑몰 고객센터(CS)팀에서 업무 자동화를 맡고 있거든

[상황]
- 매일 아침 전날 들어온 고객 문의를 CSV로 내려받아, 문의 유형을 분류하고 답변 초안을 만드는 스크립트를 돌리고 있음
- 상담원은 이 초안을 보고 다듬어서 고객에게 보내
- LangChain 0.0.3xx 버전으로 만들었는데, 회사 공통 파이썬 환경이 LangChain 1.x로 바뀌어서 이 스크립트를 고쳐야 함 ㅠ

[요청]
아래 코드를 LangChain 1.x에서 동작하도록 수정하셈

[지켜야 할 조건]
1. classify는 지금처럼 CATEGORIES 중 하나의 문자열을 반환해야 함
2. draft_reply는 {"category": 문자열, "reply": 문자열} 형태의 dict를 반환해야 함 상담원용 화면이 이 형식을 그대로 읽어
3. 프롬프트 문구, CATEGORIES, CSV 읽기/쓰기 부분은 바꾸지마
4. 바꾼 줄마다 이유를 알려 주시고, 새로 설치해야 하는 패키지가 있으면 알려줘 

```python
import csv

from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

CATEGORIES = ["배송", "환불", "회원정보", "기타"]

llm = ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0)

reply_prompt = PromptTemplate.from_template(
    "너는 쇼핑몰 고객센터 상담원이야. 아래 문의에 정중한 답변 초안을 작성해.\\n"
    "문의 유형: {category}\\n"
    "고객 문의: {inquiry}"
)
reply_chain = LLMChain(llm=llm, prompt=reply_prompt)


def classify(inquiry: str) -> str:
    answer = llm.predict(f"다음 고객 문의를 {CATEGORIES} 중 하나로만 분류해서 단어만 답해: {inquiry}")
    return answer.strip() if answer.strip() in CATEGORIES else "기타"


def draft_reply(inquiry: str) -> dict:
    category = classify(inquiry)
    reply = reply_chain.run(category=category, inquiry=inquiry)
    return {"category": category, "reply": reply}


def process_csv(src: str, dst: str) -> int:
    with open(src, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    with open(dst, "w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=["inquiry", "category", "reply"])
        writer.writeheader()
        for row in rows:
            writer.writerow({"inquiry": row["inquiry"], **draft_reply(row["inquiry"])})
    return len(rows)


if __name__ == "__main__":
    print(draft_reply("주문한 지 일주일이 지났는데 아직 배송이 안 왔어요."))
    count = process_csv("inquiries.csv", "drafts.csv")
    print(f"{count}건 답변 초안 생성 완료")
```"""

    # supervisor = migration_pipeline()
    # result = supervisor.invoke({ "question": question })
    result = supervisor.invoke({ "messages": [HumanMessage(content=question)] })

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