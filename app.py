from src.graph.supervisor import migration_pipeline

def main():
    supervisor = migration_pipeline()
    result = supervisor.invoke({
            "question": """
LangChain 버전 0.0.300의 코드를 1.0 이상의 코드로 migration하고 싶어. 아래 코드를 수정해줄 수 있어?

from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

llm = ChatOpenAI(temperature=0)
prompt = PromptTemplate.from_template("product을 만드는 회사 이름을 지어줘")
chain = LLMChain(llm=llm, prompt=prompt)
print(chain.run(product="양말"))
"""
        }
    )

    print("\n[응답]")
    print(result.get("new_code") or result.get("old_code"))
    print(result.get("analysis") or None)

if __name__ == "__main__":
    main()