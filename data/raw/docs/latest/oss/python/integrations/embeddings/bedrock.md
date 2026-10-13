> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# BedrockEmbeddings integration

> Integrate with the BedrockEmbeddings embedding model using LangChain Python.

> [Amazon Bedrock](https://aws.amazon.com/bedrock/) is a fully managed service that offers a choice of
> high-performing foundation models (FMs) from leading AI companies like `AI21 Labs`, `Anthropic`, `Cohere`,
> `Meta`, `Stability AI`, and `Amazon` via a single API, along with a broad set of capabilities you need to
> build generative AI applications with security, privacy, and responsible AI. Using `Amazon Bedrock`,
> you can easily experiment with and evaluate top FMs for your use case, privately customize them with
> your data using techniques such as fine-tuning and `Retrieval Augmented Generation` (`RAG`), and build
> agents that execute tasks using your enterprise systems and data sources. Since `Amazon Bedrock` is
> serverless, you don't have to manage any infrastructure, and you can securely integrate and deploy
> generative AI capabilities into your applications using the AWS services you are already familiar with.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
pip install -qU  boto3
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_aws import BedrockEmbeddings

embeddings = BedrockEmbeddings(
    credentials_profile_name="bedrock-admin", region_name="us-east-1"
)
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
embeddings.embed_query("This is a content of the document")
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
embeddings.embed_documents(
    ["This is a content of the document", "This is another document"]
)
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# async embed query
await embeddings.aembed_query("This is a content of the document")
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# async embed documents
await embeddings.aembed_documents(
    ["This is a content of the document", "This is another document"]
)
```

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/embeddings/bedrock.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
