"""메서드 대응표 직접 보강분.

자동 추출(@deprecated 메서드)만으로는 빠지는 두 가지를 채운다.
1. METHOD_NOTES: 자동 추출된 메서드에 붙일 설명 — 반환값 차이처럼 rewriter 가 놓치기 쉬운 점과
   공식 문서 근거(doc_refs: 문서 경로, 4단계 청크의 path 와 같은 값)
2. MANUAL_METHODS: 공식 @deprecated 표시가 없지만 구버전 코드에 흔한 패턴
   (메모리 save_context, LLMChain.predict 등). 모두 공식 마이그레이션 문서를 근거로 단다.

설명(note)은 rewriter LLM 에 그대로 들어가므로 영어로 쓴다.
"""

# 메서드 이름 → 설명/근거 (같은 이름이면 클래스가 달라도 공통으로 붙는다)
METHOD_NOTES: dict[str, dict] = {
    "run": {
        "note": "chain.run(x) returned only the output string. chain.invoke({...}) takes a dict and returns a dict "
                "(read the output key, e.g. result['text']), or rebuild the chain with LCEL "
                "(prompt | llm | StrOutputParser()) so invoke returns a string.",
        "doc_refs": ["versions/migrating_chains/index", "versions/migrating_chains/llm_chain"],
    },
    "arun": {
        "note": "Async version of run. Use await chain.ainvoke({...}); the return type is a dict, not a string.",
        "doc_refs": ["versions/migrating_chains/index"],
    },
    "__call__": {
        "note": "Calling the object directly (llm('...'), chat([...]), chain({...}), tool('...')) is removed or deprecated. "
                "Call .invoke(...) instead. A chat model's invoke returns an AIMessage (use .content for text); "
                "a legacy chain's invoke returns a dict.",
        "doc_refs": ["oss/python/langchain/models", "oss/python/migrate/langchain-v1"],
    },
    "predict": {
        "note": "llm.predict(text) returned a string. model.invoke(text) on a chat model returns an AIMessage; "
                "use response.content, or append StrOutputParser() in an LCEL chain.",
        "doc_refs": ["oss/python/langchain/models"],
    },
    "predict_messages": {
        "note": "Use model.invoke(messages); it returns an AIMessage.",
        "doc_refs": ["oss/python/langchain/models"],
    },
    "call_as_llm": {
        "note": "Use model.invoke(text) and read .content from the returned AIMessage.",
        "doc_refs": ["oss/python/langchain/models"],
    },
    "apply": {
        "note": "chain.apply(list_of_inputs) is replaced by chain.batch(list_of_inputs), which returns a list of outputs.",
        "doc_refs": ["versions/migrating_chains/index"],
    },
    "get_relevant_documents": {
        "note": "retriever.get_relevant_documents(query) is removed. Use retriever.invoke(query); "
                "it still returns list[Document].",
        "doc_refs": ["oss/python/langchain/knowledge-base", "oss/python/integrations/retrievers/index"],
    },
    "aget_relevant_documents": {
        "note": "Use await retriever.ainvoke(query); it returns list[Document].",
        "doc_refs": ["oss/python/integrations/retrievers/index"],
    },
    "persist": {
        "note": "Remove the vectorstore.persist() call. langchain_chroma.Chroma persists automatically "
                "when persist_directory is set.",
        "doc_refs": ["oss/python/integrations/vectorstores/chroma"],
    },
}

# 공식 @deprecated 표시가 없는 흔한 구버전 패턴
MANUAL_METHODS: list[dict] = [
    {
        "class": "BaseChatMemory", "classes": ["ConversationBufferMemory", "ConversationBufferWindowMemory",
                                                "ConversationSummaryMemory", "ConversationTokenBufferMemory"],
        "method": "save_context", "alternative": "LangGraph checkpointer",
        "note": "Legacy memory objects are deprecated (only in langchain_classic). Instead of memory.save_context(...), "
                "build the agent with create_agent(model, tools, checkpointer=InMemorySaver()) "
                "(from langgraph.checkpoint.memory import InMemorySaver) and pass "
                "config={'configurable': {'thread_id': ...}} to invoke; history is saved automatically.",
        "doc_refs": ["oss/python/langchain/short-term-memory", "versions/migrating_memory/conversation_buffer_memory",
                     "versions/migrating_memory/index"],
    },
    {
        "class": "BaseChatMemory", "classes": ["ConversationBufferMemory", "ConversationBufferWindowMemory",
                                                "ConversationSummaryMemory", "ConversationTokenBufferMemory"],
        "method": "load_memory_variables", "alternative": "LangGraph checkpointer",
        "note": "Instead of memory.load_memory_variables({}), let the checkpointer keep the message history per "
                "thread_id; read past messages from the agent state (result['messages']).",
        "doc_refs": ["oss/python/langchain/short-term-memory", "versions/migrating_memory/conversation_buffer_memory"],
    },
    {
        "class": "LLMChain", "classes": ["LLMChain"],
        "method": "predict", "alternative": "LCEL invoke",
        "note": "LLMChain(llm=llm, prompt=prompt).predict(**kwargs) becomes "
                "(prompt | llm | StrOutputParser()).invoke({...}), which returns a string.",
        "doc_refs": ["versions/migrating_chains/llm_chain"],
    },
    {
        "class": "ConversationChain", "classes": ["ConversationChain"],
        "method": "predict", "alternative": "create_agent with checkpointer",
        "note": "ConversationChain(llm=llm, memory=...).predict(input=...) becomes an agent or chain with "
                "persistence: create_agent(model, tools=[], checkpointer=InMemorySaver()) and "
                "agent.invoke({'messages': [...]}, config={'configurable': {'thread_id': ...}}).",
        "doc_refs": ["versions/migrating_chains/conversation_chain", "oss/python/langchain/short-term-memory"],
    },
    {
        "class": "AgentExecutor", "classes": ["AgentExecutor", "initialize_agent"],
        "method": "run", "alternative": "create_agent(...).invoke",
        "note": "initialize_agent(...).run(text) / AgentExecutor.run(text) becomes "
                "agent = create_agent(model, tools, system_prompt=...); "
                "agent.invoke({'messages': [{'role': 'user', 'content': text}]}); "
                "the answer is result['messages'][-1].content.",
        "doc_refs": ["oss/python/migrate/langchain-v1", "how_to/migrate_agent", "oss/python/langchain/agents"],
    },
]
