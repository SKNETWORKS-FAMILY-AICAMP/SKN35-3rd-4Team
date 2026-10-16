> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# ChatUpstage integration

> Integrate with the ChatUpstage chat model using LangChain Python.

This notebook covers how to get started with Upstage chat models.

## Installation

Install `langchain-upstage` package.

```bash theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
pip install -U langchain-upstage
```

## Environment setup

Make sure to set the following environment variables:

* `UPSTAGE_API_KEY`: Your Upstage API key from [Upstage console](https://console.upstage.ai/).

## Usage

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import os

os.environ["UPSTAGE_API_KEY"] = "YOUR_API_KEY"
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_core.prompts import ChatPromptTemplate
from langchain_upstage import ChatUpstage

chat = ChatUpstage()
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# using chat invoke
chat.invoke("Hello, how are you?")
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# using chat stream
stream = chat.stream_events("Hello, how are you?", version="v3")
for token in stream.text:
    print(token, end="", flush=True)
```

## Chaining

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# using chain
prompt = ChatPromptTemplate.from_messages(
    [
        ("system", "You are a helpful assistant that translates English to French."),
        ("human", "Translate this sentence from English to French. {english_text}."),
    ]
)
chain = prompt | chat

chain.invoke({"english_text": "Hello, how are you?"})
```

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/chat/upstage.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
