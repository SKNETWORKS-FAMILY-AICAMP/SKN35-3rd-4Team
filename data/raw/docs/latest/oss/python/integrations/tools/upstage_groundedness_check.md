> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Upstage groundedness check integration

> Integrate with the Upstage groundedness check tool using LangChain Python.

This notebook covers how to get started with Upstage groundedness check models.

## Installation

Install `langchain-upstage` package.

```bash theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
pip install -U langchain-upstage
```

## Environment setup

Make sure to set the following environment variables:

* `UPSTAGE_API_KEY`: Your Upstage API key from [Upstage developers document](https://developers.upstage.ai/docs/getting-started/quick-start).

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import os

os.environ["UPSTAGE_API_KEY"] = "YOUR_API_KEY"
```

## Usage

Initialize `UpstageGroundednessCheck` class.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_upstage import UpstageGroundednessCheck

groundedness_check = UpstageGroundednessCheck()
```

Use the `run` method to check the groundedness of the input text.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
request_input = {
    "context": "Mauna Kea is an inactive volcano on the island of Hawai'i. Its peak is 4,207.3 m above sea level, making it the highest point in Hawaii and second-highest peak of an island on Earth.",
    "answer": "Mauna Kea is 5,207.3 meters tall.",
}

response = groundedness_check.invoke(request_input)
print(response)
```

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/tools/upstage_groundedness_check.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
