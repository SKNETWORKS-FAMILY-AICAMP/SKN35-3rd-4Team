"""실무형 질문 36개 (eval/questions.json) 를 만든다. 내용을 고칠 때는 이 파일을 고치고 다시 실행한다.

    python eval/build_questions.py
"""
import json
from pathlib import Path

Q = []


def q(type_, difficulty, request, code, expected_imports, checks, source="unknown", target="1.x"):
    Q.append({"id": f"q{len(Q) + 1:02d}", "type": type_, "difficulty": difficulty, "source_version": source,
              "target_version": target, "request": request, "code": code.strip("\n") + "\n",
              "expected_imports": expected_imports, "checks": checks})


# A. import 경로 이동
q("import 경로", "쉬움", "회사 서버가 langchain 1.x로 올라가서 이 코드가 안 돌아가요. import만 고쳐 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.prompts import PromptTemplate

llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)
prompt = PromptTemplate.from_template("{topic}을 한 문장으로 설명해줘")
print(llm.invoke(prompt.format(topic="벡터 DB")).content)
''', ["from langchain_openai import ChatOpenAI", "from langchain_core.prompts import PromptTemplate"],
  ["langchain.chat_models 없음", "langchain.prompts 없음"], "0.1.20")
q("import 경로", "쉬움", "메시지 객체 import에서 에러가 나요. 최신 경로로 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.schema import HumanMessage, SystemMessage

chat = ChatOpenAI(temperature=0)
msgs = [SystemMessage(content="너는 번역가야"), HumanMessage(content="Hello를 한국어로")]
print(chat.invoke(msgs).content)
''', ["from langchain_openai import ChatOpenAI", "from langchain_core.messages import HumanMessage, SystemMessage"],
  ["langchain.schema 없음"], "0.0.354")
q("import 경로", "쉬움", "Document 만들어서 쓰는 부분인데 0.3 코드예요. 1.x로 바꿔 주세요.", '''
from langchain.schema import Document
from langchain.prompts import ChatPromptTemplate

docs = [Document(page_content="LangChain 1.0 출시", metadata={"src": "news"})]
prompt = ChatPromptTemplate.from_messages([("system", "요약가"), ("human", "{text}")])
print(prompt.format_messages(text=docs[0].page_content))
''', ["from langchain_core.documents import Document", "from langchain_core.prompts import ChatPromptTemplate"],
  ["langchain.schema 없음"], "0.3.30")

# B. 문서 로더 · 분할기
q("문서 로더 · 분할기", "쉬움", "PDF 읽어서 자르는 전처리 코드인데 최신 버전에 맞게 고쳐 주세요.", '''
from langchain.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

docs = PyPDFLoader("manual.pdf").load()
splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=50)
chunks = splitter.split_documents(docs)
print(len(chunks))
''', ["from langchain_community.document_loaders import PyPDFLoader",
      "from langchain_text_splitters import RecursiveCharacterTextSplitter"],
  ["langchain.document_loaders 없음", "langchain.text_splitter 없음"], "0.1.20")
q("문서 로더 · 분할기", "쉬움", "웹페이지 크롤링해서 글자 수 기준으로 자르는 코드예요. 1.x로 옮겨 주세요.", '''
from langchain.document_loaders import WebBaseLoader
from langchain.text_splitter import CharacterTextSplitter

docs = WebBaseLoader("https://example.com").load()
chunks = CharacterTextSplitter(separator="\\n", chunk_size=300).split_documents(docs)
''', ["from langchain_community.document_loaders import WebBaseLoader",
      "from langchain_text_splitters import CharacterTextSplitter"],
  ["langchain.document_loaders 없음"], "0.0.354")
q("문서 로더 · 분할기", "중간", "폴더 안 txt 파일을 전부 읽어 오는 코드인데, 어디가 바뀌었는지도 같이 알려 주세요.", '''
from langchain.document_loaders import DirectoryLoader, TextLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter

loader = DirectoryLoader("./notes", glob="**/*.txt", loader_cls=TextLoader)
docs = loader.load()
chunks = RecursiveCharacterTextSplitter(chunk_size=800).split_documents(docs)
''', ["from langchain_community.document_loaders import DirectoryLoader, TextLoader",
      "from langchain_text_splitters import RecursiveCharacterTextSplitter"],
  ["바뀐 이유 설명 포함"], "0.2.17")

# C. 임베딩 · 벡터스토어
q("임베딩 · 벡터스토어", "쉬움", "FAISS로 벡터 DB 만드는 코드가 import 에러가 나요.", '''
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

db = FAISS.from_texts(["사과는 빨갛다", "바나나는 노랗다"], OpenAIEmbeddings())
print(db.similarity_search("노란 과일", k=1))
''', ["from langchain_openai import OpenAIEmbeddings", "from langchain_community.vectorstores import FAISS"],
  ["langchain.embeddings 없음", "langchain.vectorstores 없음"], "0.1.20")
q("임베딩 · 벡터스토어", "중간", "검색기(retriever) 쓰는 부분까지 최신 방식으로 바꿔 주세요. get_relevant_documents가 경고가 떠요.", '''
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS

db = FAISS.from_texts(["환불은 7일 이내", "배송은 2일"], OpenAIEmbeddings())
retriever = db.as_retriever(search_kwargs={"k": 1})
print(retriever.get_relevant_documents("환불 기간"))
''', ["from langchain_openai import OpenAIEmbeddings", "from langchain_community.vectorstores import FAISS"],
  ["get_relevant_documents → invoke"], "0.2.17")
q("임베딩 · 벡터스토어", "중간", "허깅페이스 임베딩 쓰는 코드인데 패키지가 바뀌었다고 들었어요. 뭘 설치해야 하는지도 알려 주세요.", '''
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS

emb = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
db = FAISS.from_texts(["안녕하세요"], emb)
''', ["from langchain_huggingface import HuggingFaceEmbeddings", "from langchain_community.vectorstores import FAISS"],
  ["설치 패키지 안내(langchain-huggingface)"], "0.2.17")

# D. LLMChain → LCEL
q("LLMChain → LCEL", "중간", "회의록 요약 체인인데 결과에서 ['text']를 꺼내 쓰고 있어요. 1.x에서도 문자열로 받게 해 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.prompts import ChatPromptTemplate
from langchain.chains import LLMChain

prompt = ChatPromptTemplate.from_messages([
    ("system", "너는 사내 회의록 요약 담당이야."),
    ("human", "다음 회의록을 세 줄로 요약해 줘:\\n{minutes}"),
])
chain = LLMChain(llm=ChatOpenAI(model_name="gpt-3.5-turbo", temperature=0), prompt=prompt)
result = chain.invoke({"minutes": "배포 일정 확정, QA 인원 2명 추가, 다음 회의는 금요일"})
print(result["text"])
''', ["from langchain_openai import ChatOpenAI", "from langchain_core.prompts import ChatPromptTemplate",
      "from langchain_core.output_parsers import StrOutputParser"],
  ["LLMChain 없음", "result['text'] 대신 문자열 결과(StrOutputParser)", "model_name → model"], "0.1.20")
q("LLMChain → LCEL", "중간", "predict랑 apply 쓰는 옛날 체인이에요. 여러 입력을 한 번에 돌리는 부분도 살려 주세요.", '''
from langchain.llms import OpenAI
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate

chain = LLMChain(llm=OpenAI(temperature=0), prompt=PromptTemplate.from_template("{word}의 반대말은?"))
print(chain.predict(word="크다"))
print(chain.apply([{"word": "빠르다"}, {"word": "높다"}]))
''', ["from langchain_openai import OpenAI", "from langchain_core.prompts import PromptTemplate",
      "from langchain_core.output_parsers import StrOutputParser"],
  [".predict → invoke", ".apply → batch"], "0.0.300")
q("LLMChain → LCEL", "중간", "프롬프트 결과를 바로 JSON으로 받는 체인인데 1.x 스타일로 정리해 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain
from langchain.prompts import ChatPromptTemplate
from langchain.output_parsers.json import SimpleJsonOutputParser

prompt = ChatPromptTemplate.from_template("{city}의 인구와 면적을 JSON으로")
chain = LLMChain(llm=ChatOpenAI(), prompt=prompt, output_parser=SimpleJsonOutputParser())
print(chain.run(city="서울"))
''', ["from langchain_openai import ChatOpenAI", "from langchain_core.prompts import ChatPromptTemplate",
      "from langchain_core.output_parsers import JsonOutputParser"],
  ["output_parser= 인자 대신 | 로 연결"], "0.1.20")

# E. 체인 조합
q("체인 조합", "중간", "SimpleSequentialChain으로 두 단계 이어 붙인 코드예요. 최신 방식으로 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain, SimpleSequentialChain
from langchain.prompts import PromptTemplate

llm = ChatOpenAI(temperature=0)
idea = LLMChain(llm=llm, prompt=PromptTemplate.from_template("{topic} 블로그 제목 하나"))
outline = LLMChain(llm=llm, prompt=PromptTemplate.from_template("제목 '{title}'의 목차 3개"))
print(SimpleSequentialChain(chains=[idea, outline]).run("벡터 검색"))
''', ["from langchain_openai import ChatOpenAI", "from langchain_core.prompts import PromptTemplate",
      "from langchain_core.output_parsers import StrOutputParser"],
  ["SimpleSequentialChain 없음 → | 로 연결"], "0.0.354")
q("체인 조합", "어려움", "SequentialChain에서 중간 결과 여러 개를 같이 넘기는데, 이 출력 키들을 유지하면서 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.chains import LLMChain, SequentialChain
from langchain.prompts import PromptTemplate

llm = ChatOpenAI(temperature=0)
summ = LLMChain(llm=llm, prompt=PromptTemplate.from_template("요약: {review}"), output_key="summary")
tone = LLMChain(llm=llm, prompt=PromptTemplate.from_template("감정 분류: {summary}"), output_key="tone")
chain = SequentialChain(chains=[summ, tone], input_variables=["review"], output_variables=["summary", "tone"])
print(chain({"review": "배송은 느렸지만 품질은 좋아요"}))
''', ["from langchain_openai import ChatOpenAI", "from langchain_core.prompts import PromptTemplate",
      "from langchain_core.runnables import RunnablePassthrough"],
  ["summary, tone 두 키 유지", "chain({...}) 호출 → invoke"], "0.2.17")
q("체인 조합", "어려움", "주제에 따라 다른 프롬프트로 보내는 라우터 체인이에요. 1.x에서 어떻게 해야 해요?", '''
from langchain.chat_models import ChatOpenAI
from langchain.chains.router import MultiPromptChain

infos = [
    {"name": "math", "description": "수학 질문", "prompt_template": "수학 선생님으로 답해: {input}"},
    {"name": "history", "description": "역사 질문", "prompt_template": "역사학자로 답해: {input}"},
]
chain = MultiPromptChain.from_prompts(ChatOpenAI(temperature=0), infos)
print(chain.run("임진왜란은 언제야?"))
''', ["from langchain_openai import ChatOpenAI", "from langchain_core.prompts import PromptTemplate",
      "from langchain_core.runnables import RunnableBranch"],
  ["MultiPromptChain 없음 → RunnableBranch 또는 분기 함수"], "0.1.20")

# F. RAG
q("RAG", "중간", "사내 문서 QA 봇이 RetrievalQA로 돼 있어요. 1.x 방식으로 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import RetrievalQA

db = FAISS.from_texts(["연차는 15일", "점심은 12시"], OpenAIEmbeddings())
qa = RetrievalQA.from_chain_type(llm=ChatOpenAI(temperature=0), retriever=db.as_retriever())
print(qa.run("연차 며칠이야?"))
''', ["from langchain_openai import ChatOpenAI, OpenAIEmbeddings", "from langchain_community.vectorstores import FAISS",
      "from langchain_core.prompts import ChatPromptTemplate", "from langchain_core.runnables import RunnablePassthrough"],
  ["RetrievalQA 없음 → 검색 | 프롬프트 | 모델"], "0.1.20")
q("RAG", "어려움", "대화 기록을 기억하는 문서 QA예요(ConversationalRetrievalChain). 기록 유지 기능은 꼭 살려 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.embeddings import OpenAIEmbeddings
from langchain.vectorstores import FAISS
from langchain.chains import ConversationalRetrievalChain
from langchain.memory import ConversationBufferMemory

db = FAISS.from_texts(["제품 A 가격은 1만원"], OpenAIEmbeddings())
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
qa = ConversationalRetrievalChain.from_llm(ChatOpenAI(), db.as_retriever(), memory=memory)
print(qa({"question": "제품 A 가격은?"}))
''', ["from langchain_openai import ChatOpenAI, OpenAIEmbeddings", "from langchain_community.vectorstores import FAISS"],
  ["대화 기록 유지 방법 제시(체크포인터 등)", "ConversationalRetrievalChain 없음"], "0.2.17")
q("RAG", "중간", "load_qa_chain으로 문서 몇 개 넣고 답하는 코드예요. stuff 방식 그대로 유지해 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.chains.question_answering import load_qa_chain
from langchain.schema import Document

docs = [Document(page_content="회의는 매주 월요일 10시")]
chain = load_qa_chain(ChatOpenAI(temperature=0), chain_type="stuff")
print(chain.run(input_documents=docs, question="회의 언제야?"))
''', ["from langchain_openai import ChatOpenAI", "from langchain_core.documents import Document",
      "from langchain_core.prompts import ChatPromptTemplate"],
  ["load_qa_chain 없음 → 문서를 프롬프트에 넣는 LCEL"], "0.1.20")

# G. 메모리
q("메모리", "중간", "ConversationChain으로 만든 상담 챗봇인데, 대화 기억은 그대로 두고 1.x로 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory

conv = ConversationChain(llm=ChatOpenAI(temperature=0), memory=ConversationBufferMemory())
print(conv.predict(input="내 이름은 민수야"))
print(conv.predict(input="내 이름이 뭐였지?"))
''', ["from langchain_openai import ChatOpenAI"],
  ["ConversationChain 없음", "대화 기억 유지(체크포인터 또는 메시지 기록)"], "0.0.300")
q("메모리", "어려움", "최근 3턴만 기억하는 창 메모리를 쓰고 있어요. 같은 동작을 1.x에서 어떻게 하죠?", '''
from langchain.chat_models import ChatOpenAI
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferWindowMemory

conv = ConversationChain(llm=ChatOpenAI(), memory=ConversationBufferWindowMemory(k=3))
for msg in ["안녕", "날씨 어때", "점심 추천", "내가 처음에 뭐라 했지?"]:
    print(conv.predict(input=msg))
''', ["from langchain_openai import ChatOpenAI", "from langchain_core.messages import trim_messages"],
  ["최근 k턴만 유지하는 방법(trim_messages 등)"], "0.1.20")
q("메모리", "중간", "세션별로 대화 기록을 따로 저장해야 해요. 지금 코드를 최신 방식으로 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.memory import ConversationBufferMemory
from langchain.chains import ConversationChain

sessions = {}
def chat(session_id, text):
    if session_id not in sessions:
        sessions[session_id] = ConversationChain(llm=ChatOpenAI(), memory=ConversationBufferMemory())
    return sessions[session_id].predict(input=text)
''', ["from langchain_openai import ChatOpenAI", "from langgraph.checkpoint.memory import InMemorySaver"],
  ["세션 구분(thread_id 등) 유지"], "0.2.17")

# H. 에이전트 · 도구
q("에이전트 · 도구", "어려움", "initialize_agent로 만든 계산기 에이전트예요. 1.x에서 에이전트 만드는 방식으로 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.agents import initialize_agent, AgentType, Tool

def add(q: str) -> str:
    a, b = q.split("+")
    return str(int(a) + int(b))

tools = [Tool(name="add", func=add, description="두 수 더하기. 입력 예: 3+4")]
agent = initialize_agent(tools, ChatOpenAI(temperature=0), agent=AgentType.ZERO_SHOT_REACT_DESCRIPTION)
print(agent.run("12+30은?"))
''', ["from langchain_openai import ChatOpenAI", "from langchain.agents import create_agent",
      "from langchain_core.tools import tool"],
  ["initialize_agent 없음 → create_agent", "Tool → @tool"], "0.0.300")
q("에이전트 · 도구", "어려움", "AgentExecutor랑 create_openai_tools_agent 쓰는 코드예요. 최신 권장 방식으로 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain.tools import tool
from langchain import hub

@tool
def weather(city: str) -> str:
    """도시의 날씨"""
    return f"{city}는 맑음"

prompt = hub.pull("hwchase17/openai-tools-agent")
agent = create_openai_tools_agent(ChatOpenAI(), [weather], prompt)
print(AgentExecutor(agent=agent, tools=[weather]).invoke({"input": "서울 날씨"}))
''', ["from langchain_openai import ChatOpenAI", "from langchain.agents import create_agent",
      "from langchain_core.tools import tool"],
  ["hub.pull 의존 제거", "AgentExecutor 없음"], "0.1.20")
q("에이전트 · 도구", "어려움", "도구 호출 에이전트에 대화 기억까지 붙인 코드예요. 기억 기능 포함해서 1.x로 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain.memory import ConversationBufferMemory
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain.tools import tool

@tool
def stock(code: str) -> str:
    """재고 수량 조회"""
    return "12개"

prompt = ChatPromptTemplate.from_messages([("system", "재고 도우미"), MessagesPlaceholder("chat_history"),
                                           ("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
agent = create_tool_calling_agent(ChatOpenAI(), [stock], prompt)
memory = ConversationBufferMemory(memory_key="chat_history", return_messages=True)
executor = AgentExecutor(agent=agent, tools=[stock], memory=memory)
print(executor.invoke({"input": "A100 재고?"}))
''', ["from langchain_openai import ChatOpenAI", "from langchain.agents import create_agent",
      "from langchain_core.tools import tool", "from langgraph.checkpoint.memory import InMemorySaver"],
  ["메모리 → 체크포인터", "AgentExecutor 없음"], "0.2.17")

# I. 출력 파서 · 구조화 출력
q("출력 파서", "중간", "ResponseSchema로 결과를 dict로 받는 코드예요. 요즘 방식(구조화 출력)으로 바꿔 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import StructuredOutputParser, ResponseSchema
from langchain.prompts import PromptTemplate

schemas = [ResponseSchema(name="name", description="제품명"), ResponseSchema(name="price", description="가격")]
parser = StructuredOutputParser.from_response_schemas(schemas)
prompt = PromptTemplate.from_template("문장에서 제품 정보 추출: {text}\\n{fmt}")
out = ChatOpenAI().invoke(prompt.format(text="아이폰 15는 120만원", fmt=parser.get_format_instructions()))
print(parser.parse(out.content))
''', ["from langchain_openai import ChatOpenAI", "from pydantic import BaseModel"],
  ["with_structured_output 또는 동등한 방식"], "0.1.20")
q("출력 파서", "중간", "Pydantic 파서 쓰는 코드인데 langchain.pydantic_v1에서 에러가 나요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.output_parsers import PydanticOutputParser
from langchain.pydantic_v1 import BaseModel, Field

class Movie(BaseModel):
    title: str = Field(description="제목")
    year: int = Field(description="개봉 연도")

parser = PydanticOutputParser(pydantic_object=Movie)
print(parser.get_format_instructions())
''', ["from langchain_core.output_parsers import PydanticOutputParser", "from pydantic import BaseModel, Field"],
  ["pydantic_v1 → pydantic"], "0.2.17")
q("출력 파서", "쉬움", "쉼표로 구분된 목록 파서예요. 경로만 바뀐 건지 확인하고 고쳐 주세요.", '''
from langchain.output_parsers import CommaSeparatedListOutputParser
from langchain.prompts import PromptTemplate

parser = CommaSeparatedListOutputParser()
prompt = PromptTemplate.from_template("{thing} 5개를 쉼표로")
print(parser.parse("사과, 배, 감"))
''', ["from langchain_core.output_parsers import CommaSeparatedListOutputParser",
      "from langchain_core.prompts import PromptTemplate"],
  ["경로만 바뀜 확인"], "0.1.20")

# J. 실무 상황형
q("실무 상황", "중간", "실행하니까 ImportError: cannot import name 'ChatOpenAI' from 'langchain.chat_models' 라고 떠요. 왜 그런지 설명하고 고쳐 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler

llm = ChatOpenAI(streaming=True, callbacks=[StreamingStdOutCallbackHandler()])
llm.invoke("짧은 시 한 편")
''', ["from langchain_openai import ChatOpenAI",
      "from langchain_core.callbacks import StreamingStdOutCallbackHandler"],
  ["에러 원인 설명 포함", "스트리밍 유지"], "0.1.20")
q("실무 상황", "중간", "LLM 응답 캐시를 켜 두는 설정 코드예요. 전역 캐시 설정 방식이 바뀌었다는데 고쳐 주세요.", '''
import langchain
from langchain.cache import InMemoryCache
from langchain.chat_models import ChatOpenAI

langchain.llm_cache = InMemoryCache()
llm = ChatOpenAI()
llm.invoke("안녕")
''', ["from langchain_core.caches import InMemoryCache", "from langchain_core.globals import set_llm_cache",
      "from langchain_openai import ChatOpenAI"],
  ["langchain.llm_cache 대입 → set_llm_cache"], "0.0.300")
q("실무 상황", "어려움", "긴 보고서를 map_reduce로 요약하는 배치 코드예요. 결과는 같게, 코드는 1.x로 바꿔 주세요. 꼭 못 바꾸는 부분이 있으면 알려 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.chains.summarize import load_summarize_chain
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.docstore.document import Document

text = open("report.txt", encoding="utf-8").read()
docs = [Document(page_content=t) for t in RecursiveCharacterTextSplitter(chunk_size=2000).split_text(text)]
chain = load_summarize_chain(ChatOpenAI(temperature=0), chain_type="map_reduce")
print(chain.run(docs))
''', ["from langchain_openai import ChatOpenAI", "from langchain_text_splitters import RecursiveCharacterTextSplitter",
      "from langchain_core.documents import Document"],
  ["못 바꾸는 부분 안내(unresolved) 또는 map-reduce 재구성"], "0.1.20")

# K. 버전 오가기 (옛 버전으로 되돌리기 · 중간 버전까지만 · 없는 기능)
q("버전 오가기", "중간", "운영 서버가 langchain 0.2에 고정돼 있어요. 1.x로 짠 이 코드를 0.2에서 돌게 되돌려 주세요.", '''
from langchain_openai import ChatOpenAI
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser
from langchain_text_splitters import RecursiveCharacterTextSplitter

chunks = RecursiveCharacterTextSplitter(chunk_size=500).split_text(open("faq.txt", encoding="utf-8").read())
prompt = ChatPromptTemplate.from_template("다음 FAQ를 요약해줘: {text}")
chain = prompt | ChatOpenAI(temperature=0) | StrOutputParser()
print(chain.invoke({"text": chunks[0]}))
''', ["from langchain.chat_models import ChatOpenAI", "from langchain_core.prompts import ChatPromptTemplate",
      "from langchain_core.output_parsers import StrOutputParser",
      "from langchain.text_splitter import RecursiveCharacterTextSplitter"],
  ["0.2에 없는 패키지 경로(langchain_openai · langchain_text_splitters) 되돌리기", "| 체인은 0.2에서도 그대로"],
  "1.x", "0.2.17")
q("버전 오가기", "어려움", "create_agent로 만든 에이전트인데, 고객사가 0.3을 써서 0.3에서 돌아가게 해 주세요. 안 되는 부분은 대안을 알려 주세요.", '''
from langchain_openai import ChatOpenAI
from langchain.agents import create_agent
from langchain_core.tools import tool

@tool
def order_status(order_id: str) -> str:
    """주문 상태 조회"""
    return "배송 중"

agent = create_agent(ChatOpenAI(model="gpt-4o-mini"), tools=[order_status], system_prompt="주문 도우미")
print(agent.invoke({"messages": [{"role": "user", "content": "A-17 주문 어디야?"}]}))
''', ["from langchain.chat_models import ChatOpenAI", "from langchain_core.tools import tool"],
  ["create_agent는 0.3에 없음 → 못 바꿈 표시 + 대안(create_tool_calling_agent + AgentExecutor) 안내"],
  "1.x", "0.3.30")
q("버전 오가기", "중간", "1.x에서 langchain_classic으로 겨우 돌려 둔 에이전트 코드예요. 사내 표준이 0.1이라 0.1 방식으로 되돌려 주세요.", '''
from langchain_openai import ChatOpenAI
from langchain_classic.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([("system", "도우미"), ("human", "{input}"),
                                           MessagesPlaceholder("agent_scratchpad")])
agent = create_tool_calling_agent(ChatOpenAI(), [], prompt)
print(AgentExecutor(agent=agent, tools=[]).invoke({"input": "안녕"}))
''', ["from langchain.chat_models import ChatOpenAI", "from langchain.agents import AgentExecutor, create_tool_calling_agent",
      "from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder"],
  ["langchain_classic → langchain.agents 로 되돌리기"], "1.x", "0.1.20")
q("버전 오가기", "중간", "0.3에서 init_chat_model로 모델을 고르게 해 뒀는데, 0.1 서버로 옮겨야 해요. 안 되는 게 있으면 바꿔 쓰는 방법도요.", '''
from langchain.chat_models import init_chat_model
from langchain_core.prompts import PromptTemplate

llm = init_chat_model("gpt-4o-mini", model_provider="openai", temperature=0)
prompt = PromptTemplate.from_template("{q}에 한 줄로 답해")
print((prompt | llm).invoke({"q": "LCEL이 뭐야"}).content)
''', ["from langchain_core.prompts import PromptTemplate"],
  ["init_chat_model은 0.1에 없음 → 못 바꿈 표시 + 모델 클래스(ChatOpenAI) 직접 생성 안내"], "0.3.30", "0.1.20")
q("버전 오가기", "어려움", "신입 교육 자료가 0.0.354 기준이라, 0.3 코드를 그 버전으로 맞춰야 해요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

prompt = ChatPromptTemplate.from_messages([("human", "{input}"), MessagesPlaceholder("agent_scratchpad")])
agent = create_tool_calling_agent(ChatOpenAI(), [], prompt)
executor = AgentExecutor(agent=agent, tools=[])
''', ["from langchain.chat_models import ChatOpenAI", "from langchain.agents import AgentExecutor",
      "from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder"],
  ["create_tool_calling_agent는 0.0.354에 없음 → 못 바꿈 표시 + 그 시기 방식(OpenAI functions 에이전트 등) 안내"],
  "0.3.30", "0.0.354")
q("버전 오가기", "중간", "0.0.300 코드인데 한 번에 1.x는 부담이라 일단 0.2까지만 올리고 싶어요. 0.2에서 안 되는 것만 알려 주세요.", '''
from langchain.chat_models import ChatOpenAI
from langchain.agents import create_csv_agent

agent = create_csv_agent(ChatOpenAI(temperature=0), "sales.csv", verbose=True)
print(agent.run("3월 매출 합계는?"))
''', ["from langchain.chat_models import ChatOpenAI"],
  ["create_csv_agent는 0.2에 없음(langchain_experimental 로 분리) → 못 바꿈 표시 + 설치 안내", "ChatOpenAI는 0.2에서도 그대로"],
  "0.0.300", "0.2.17")

if __name__ == "__main__":
    Path(__file__).with_name("questions.json").write_text(json.dumps(Q, ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(Q), "개 저장")
