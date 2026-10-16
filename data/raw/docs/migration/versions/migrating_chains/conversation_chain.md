# Migrating from ConversationalChain

[`ConversationChain`](https://python.langchain.com/api_reference/langchain/chains/langchain.chains.conversation.base.ConversationChain.html) incorporated a memory of previous messages to sustain a stateful conversation.

Some advantages of switching to the Langgraph implementation are:

- Innate support for threads/separate sessions. To make this work with `ConversationChain`, you'd need to instantiate a separate memory class outside the chain.
- More explicit parameters. `ConversationChain` contains a hidden default prompt, which can cause confusion.
- Streaming support. `ConversationChain` only supports streaming via callbacks.

Langgraph's [checkpointing](https://langchain-ai.github.io/langgraph/how-tos/persistence/) system supports multiple threads or sessions, which can be specified via the `"thread_id"` key in its configuration parameters.

## Legacy

<details open>

```python
from langchain.chains import ConversationChain
from langchain.memory import ConversationBufferMemory
from langchain_core.prompts import ChatPromptTemplate
from langchain_openai import ChatOpenAI

template = """
You are a pirate. Answer the following questions as best you can.
Chat history: {history}
Question: {input}
"""

prompt = ChatPromptTemplate.from_template(template)

memory = ConversationBufferMemory()

chain = ConversationChain(
    llm=ChatOpenAI(),
    memory=memory,
    prompt=prompt,
)

chain({"input": "I'm Bob, how are you?"})
```

```python
chain({"input": "What is my name?"})
```

</details>

## Langgraph

<details open>

```python
import uuid

from langchain_openai import ChatOpenAI
from langgraph.checkpoint.memory import MemorySaver
from langgraph.graph import START, MessagesState, StateGraph

model = ChatOpenAI(model="gpt-4o-mini")

# Define a new graph
workflow = StateGraph(state_schema=MessagesState)


# Define the function that calls the model
def call_model(state: MessagesState):
    response = model.invoke(state["messages"])
    return {"messages": response}


# Define the two nodes we will cycle between
workflow.add_edge(START, "model")
workflow.add_node("model", call_model)

# Add memory
memory = MemorySaver()
app = workflow.compile(checkpointer=memory)


# The thread id is a unique key that identifies
# this particular conversation.
# We'll just generate a random uuid here.
thread_id = uuid.uuid4()
config = {"configurable": {"thread_id": thread_id}}
```

```python
query = "I'm Bob, how are you?"

input_messages = [
    {
        "role": "system",
        "content": "You are a pirate. Answer the following questions as best you can.",
    },
    {"role": "user", "content": query},
]
for event in app.stream({"messages": input_messages}, config, stream_mode="values"):
    event["messages"][-1].pretty_print()
```

```python
query = "What is my name?"

input_messages = [{"role": "user", "content": query}]
for event in app.stream({"messages": input_messages}, config, stream_mode="values"):
    event["messages"][-1].pretty_print()
```

</details>

## Next steps

See [this tutorial](/docs/tutorials/chatbot) for a more end-to-end guide on building with [`RunnableWithMessageHistory`](https://python.langchain.com/api_reference/core/runnables/langchain_core.runnables.history.RunnableWithMessageHistory.html).

Check out the [LCEL conceptual docs](/docs/concepts/lcel) for more background information.
