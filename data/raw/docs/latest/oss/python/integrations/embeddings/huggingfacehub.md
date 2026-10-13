> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Hugging Face integration

> Integrate with Hugging Face embedding models using LangChain Python.

LangChain supports three ways to use Hugging Face embedding models:

* **Local inference** via `HuggingFaceEmbeddings`: downloads the model and runs it in-process with [Sentence Transformers](https://sbert.net).
* **Inference Providers and dedicated Inference Endpoints** via `HuggingFaceEndpointEmbeddings`: serverless or dedicated hosted inference through Hugging Face.
* **Self-hosted at scale** via [Text Embeddings Inference (TEI)](/oss/python/integrations/embeddings/text_embeddings_inference): Hugging Face's production inference server. Point `OpenAIEmbeddings` from `langchain-openai` at TEI's OpenAI-compatible API.

Local and hosted paths use `langchain-huggingface`. Self-hosted TEI uses `langchain-openai`. All three expose the same `Embeddings` interface, so you can start local and graduate to a hosted or self-hosted deployment without changing the rest of your application.

## Setup

```shell theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
pip install -qU langchain-huggingface
```

## Local embeddings

Generate embeddings locally via `sentence-transformers`. This downloads the model weights the first time you run it.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_huggingface import HuggingFaceEmbeddings

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-mpnet-base-v2",
    encode_kwargs={"normalize_embeddings": True},
)

query_result = embeddings.embed_query("This is a test document.")
doc_result = embeddings.embed_documents(["This is a test document."])
```

See the dedicated [Sentence Transformers guide](/oss/python/integrations/embeddings/sentence_transformers) for model selection, GPU configuration, and query/document prompts.

## Hugging Face Inference Endpoints and Providers

If you prefer not to download models locally, you can access embedding models through [Hugging Face Inference Providers](https://huggingface.co/docs/inference-providers) or a dedicated [Inference Endpoint](https://huggingface.co/inference-endpoints/dedicated). Both expose open-source embedding models on Hugging Face's scalable serverless infrastructure.

First, get a token from [your Hugging Face settings](https://huggingface.co/settings/tokens):

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import os
from getpass import getpass

os.environ["HUGGINGFACEHUB_API_TOKEN"] = getpass()
```

Then use `HuggingFaceEndpointEmbeddings`:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_huggingface import HuggingFaceEndpointEmbeddings

embeddings = HuggingFaceEndpointEmbeddings(
    model="sentence-transformers/all-mpnet-base-v2"
)

query_result = embeddings.embed_query("This is a test document.")
```

To route through a specific Inference Provider (e.g., `hf-inference`, `sambanova`, `together`), pass `provider=`:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
embeddings = HuggingFaceEndpointEmbeddings(
    model="BAAI/bge-m3",
    provider="hf-inference",
)
```

The full list of providers and their supported models is in the [Inference Providers documentation](https://huggingface.co/docs/inference-providers).

## Self-hosted with Text Embeddings Inference

For production-scale serving of Sentence Transformers models on your own infrastructure, use [Text Embeddings Inference (TEI)](https://github.com/huggingface/text-embeddings-inference). TEI handles batching, GPU acceleration, and exposes an OpenAI-compatible API. See the [TEI integration guide](/oss/python/integrations/embeddings/text_embeddings_inference) for a walkthrough.

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/embeddings/huggingfacehub.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
