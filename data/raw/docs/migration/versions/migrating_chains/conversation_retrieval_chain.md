# Migrating from ConversationalRetrievalChain

The [`ConversationalRetrievalChain`](https://python.langchain.com/api_reference/langchain/chains/langchain.chains.conversational_retrieval.base.ConversationalRetrievalChain.html) was an all-in one way that combined retrieval-augmented generation with chat history, allowing you to "chat with" your documents.

Advantages of switching to the LCEL implementation are similar to the [`RetrievalQA` migration guide](./retrieval_qa.ipynb):

- Clearer internals. The `ConversationalRetrievalChain` chain hides an entire question rephrasing step which dereferences the initial query against the chat history.
  - This means the class contains two sets of configurable prompts, LLMs, etc.
- More easily return source documents.
- Support for runnable methods like streaming and async operations.

Here are equivalent implementations with custom prompts.
We'll use the following ingestion code to load a [blog post by Lilian Weng](https://lilianweng.github.io/posts/2023-06-23-agent/) on autonomous agents into a local vector store:

## Shared setup

For both versions, we'll need to load the data with the `WebBaseLoader` document loader, split it with `RecursiveCharacterTextSplitter`, and add it to an in-memory `FAISS` vector store.

We will also instantiate a chat model to use.

```python
# Load docs
from langchain_community.document_loaders import WebBaseLoader
from langchain_community.vectorstores import FAISS
from langchain_openai.chat_models import ChatOpenAI
from langchain_openai.embeddings import OpenAIEmbeddings
from langchain_text_splitters import RecursiveCharacterTextSplitter

loader = WebBaseLoader("https://lilianweng.github.io/posts/2023-06-23-agent/")
data = loader.load()

# Split
text_splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=0)
all_splits = text_splitter.split_documents(data)

# Store splits
vectorstore = FAISS.from_documents(documents=all_splits, embedding=OpenAIEmbeddings())

# LLM
llm = ChatOpenAI()
```

## Legacy

<details open>

```python
from langchain.chains import ConversationalRetrievalChain
from langchain_core.prompts import ChatPromptTemplate

condense_question_template = """
Given the following conversation and a follow up question, rephrase the follow up question to be a standalone question.

Chat History:
{chat_history}
Follow Up Input: {question}
Standalone question:"""

condense_question_prompt = ChatPromptTemplate.from_template(condense_question_template)

qa_template = """
You are an assistant for question-answering tasks.
Use the following pieces of retrieved context to answer
the question. If you don't know the answer, say that you
don't know. Use three sentences maximum and keep the
answer concise.

Chat History:
{chat_history}

Other context:
{context}

Question: {question}
"""

qa_prompt = ChatPromptTemplate.from_template(qa_template)

convo_qa_chain = ConversationalRetrievalChain.from_llm(
    llm,
    vectorstore.as_retriever(),
    condense_question_prompt=condense_question_prompt,
    combine_docs_chain_kwargs={
        "prompt": qa_prompt,
    },
)

convo_qa_chain(
    {
        "question": "What are autonomous agents?",
        "chat_history": "",
    }
)
```

</details>

## LCEL

<details open>

```python
from langchain.chains import create_history_aware_retriever, create_retrieval_chain
from langchain.chains.combine_documents import create_stuff_documents_chain

condense_question_system_template = (
    "Given a chat history and the latest user question "
    "which might reference context in the chat history, "
    "formulate a standalone question which can be understood "
    "without the chat history. Do NOT answer the question, "
    "just reformulate it if needed and otherwise return it as is."
)

condense_question_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", condense_question_system_template),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
    ]
)
history_aware_retriever = create_history_aware_retriever(
    llm, vectorstore.as_retriever(), condense_question_prompt
)

system_prompt = (
    "You are an assistant for question-answering tasks. "
    "Use the following pieces of retrieved context to answer "
    "the question. If you don't know the answer, say that you "
    "don't know. Use three sentences maximum and keep the "
    "answer concise."
    "\n\n"
    "{context}"
)

qa_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", system_prompt),
        ("placeholder", "{chat_history}"),
        ("human", "{input}"),
    ]
)
qa_chain = create_stuff_documents_chain(llm, qa_prompt)

convo_qa_chain = create_retrieval_chain(history_aware_retriever, qa_chain)

convo_qa_chain.invoke(
    {
        "input": "What are autonomous agents?",
        "chat_history": [],
    }
)
```

</details>

## Next steps

You've now seen how to migrate existing usage of some legacy chains to LCEL.

Next, check out the [LCEL conceptual docs](/docs/concepts/lcel) for more background information.
