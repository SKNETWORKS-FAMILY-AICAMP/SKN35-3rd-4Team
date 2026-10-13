> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Instructor embeddings on Hugging Face integration

> Integrate with Instructor-style embedding models on Hugging Face using LangChain Python.

> The `hkunlp/instructor-*` family introduced instruction-tuned sentence embeddings. They have been broadly superseded by modern instruction-aware models, but the original models are still available on Hugging Face and usable via the legacy `HuggingFaceInstructEmbeddings` class.

For new projects, prefer `HuggingFaceEmbeddings` from [`langchain-huggingface`](/oss/python/integrations/embeddings/sentence_transformers) with a current instruction-aware model such as `intfloat/e5-large-v2`, `Qwen/Qwen3-Embedding-0.6B`, or `BAAI/bge-m3`. Pass query and document prompts via `encode_kwargs` and `query_encode_kwargs`:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="intfloat/e5-large-v2",
    encode_kwargs={"prompt": "passage: "},
    query_encode_kwargs={"prompt": "query: "},
)
```

## Legacy Instructor usage

```shell theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
pip install -qU langchain-community InstructorEmbedding sentence-transformers
```

<Warning>
  The `langchain-community` package is no longer maintained. Examples that import from `langchain_community` may be outdated or broken. Use with caution.
</Warning>

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_community.embeddings import HuggingFaceInstructEmbeddings

embeddings = HuggingFaceInstructEmbeddings(
    query_instruction="Represent the query for retrieval: "
)

query_result = embeddings.embed_query("This is a test document.")
```

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/embeddings/instruct_embeddings.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
