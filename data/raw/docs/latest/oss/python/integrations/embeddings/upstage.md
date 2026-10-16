> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# UpstageEmbeddings integration

> Integrate with the UpstageEmbeddings embedding model using LangChain Python.

This notebook covers how to get started with Upstage embedding models.

## Installation

Install `langchain-upstage` package.

```bash theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
pip install -U langchain-upstage
```

## Environment setup

Make sure to set the following environment variables:

* `UPSTAGE_API_KEY`: Your Upstage API key from [Upstage console](https://console.upstage.ai/).

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import os

os.environ["UPSTAGE_API_KEY"] = "YOUR_API_KEY"
```

## Usage

Initialize `UpstageEmbeddings` class.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_upstage import UpstageEmbeddings

embeddings = UpstageEmbeddings(model="solar-embedding-1-large")
```

Use `embed_documents` to embed list of texts or documents.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
doc_result = embeddings.embed_documents(
    ["Sung is a professor.", "This is another document"]
)
print(doc_result)
```

Use `embed_query` to embed query string.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
query_result = embeddings.embed_query("What does Sung do?")
print(query_result)
```

Use `aembed_documents` and `aembed_query` for async operations.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# async embed query
await embeddings.aembed_query("My query to look up")
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# async embed documents
await embeddings.aembed_documents(
    ["This is a content of the document", "This is another document"]
)
```

## Using with vector store

You can use `UpstageEmbeddings` with vector store component. The following demonstrates a simple example.

<Warning>
  The `langchain-community` package is no longer maintained. Examples that import from `langchain_community` may be outdated or broken. Use with caution.
</Warning>

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_community.vectorstores import DocArrayInMemorySearch

vectorstore = DocArrayInMemorySearch.from_texts(
    ["harrison worked at kensho", "bears like to eat honey"],
    embedding=UpstageEmbeddings(model="solar-embedding-1-large"),
)
retriever = vectorstore.as_retriever()
docs = retriever.invoke("Where did Harrison work?")
print(docs)
```

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/embeddings/upstage.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
