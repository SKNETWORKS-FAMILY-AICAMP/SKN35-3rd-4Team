> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# ChatAmazonNova integration

> Integrate with the ChatAmazonNova chat model using LangChain Python.

This guide provides a quick overview for getting started with Amazon Nova [chat models](/oss/python/langchain/models). Amazon Nova models are OpenAI-compatible and accessed via the OpenAI SDK pointed at Nova's endpoint, providing seamless integration with LangChain's standard interfaces. The Amazon Nova API is free tier with rate limits.

For production deployments requiring higher throughput and enterprise features, consider using Amazon Nova models via [Amazon Bedrock](/oss/python/integrations/chat/bedrock).

You can find information about Amazon Nova's models, their features, and API details in the [Amazon Nova documentation](https://nova.amazon.com/dev/documentation).

<Tip>
  **API Reference**

  For detailed documentation of all [`ChatAmazonNova`](https://reference.langchain.com/python/langchain-amazon-nova/chat_models/ChatAmazonNova) features and configuration options, head to the [`ChatAmazonNova`](https://reference.langchain.com/python/langchain-amazon-nova/chat_models/ChatAmazonNova) API reference.

  For Amazon Nova model details and capabilities, see the [Amazon Nova documentation](https://nova.amazon.com/dev/documentation).
</Tip>

## Overview

### Integration details

| Class | Package | Serializable | JS/TS Support | Downloads | Latest Version |
| :- | :- | :-: | :-: | :-: | :-: |
| [`ChatAmazonNova`](https://reference.langchain.com/python/langchain-amazon-nova/chat_models/ChatAmazonNova) | [`langchain-amazon-nova`](https://reference.langchain.com/python/langchain-amazon-nova/) | beta | ❌ | ![PyPI - Downloads](https://img.shields.io/pypi/dm/langchain-amazon-nova?style=flat-square\&label=%20) | ![PyPI - Version](https://img.shields.io/pypi/v/langchain-amazon-nova?style=flat-square\&label=%20) |

### Model features

| [Tool calling](/oss/python/langchain/tools) | [Structured output](/oss/python/langchain/structured-output) | [Image input](/oss/python/langchain/messages#multimodal) | Audio input | Video input | [Token-level streaming](/oss/python/langchain/streaming/) | Native async | [Token usage](/oss/python/langchain/models#token-usage) | [Logprobs](/oss/python/langchain/models#log-probabilities) |
| :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: | :-: |
| ✅ | ✅ | Model-dependent | ❌ | Model-dependent (Nova 2) | ✅ | ✅ | ✅ | ❌ |

## Setup

To access Amazon Nova models, you'll need to [obtain API credentials](https://nova.amazon.com/dev) and install the [`langchain-amazon-nova`](https://reference.langchain.com/python/langchain-amazon-nova/) integration package.

### Installation

<CodeGroup>
  ```bash pip theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
  pip install -U langchain-amazon-nova
  ```

  ```bash uv theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
  uv add langchain-amazon-nova
  ```
</CodeGroup>

### Credentials

Set your Nova API credentials as environment variables:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import getpass
import os

if "NOVA_API_KEY" not in os.environ:
    os.environ["NOVA_API_KEY"] = getpass.getpass("Enter your Nova API key: ")

if "NOVA_BASE_URL" not in os.environ:
    os.environ["NOVA_BASE_URL"] = getpass.getpass("Enter your Nova base URL: ")
```

To enable automated tracing of your model calls, set your [LangSmith](/langsmith/observability) API key:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
os.environ["LANGSMITH_API_KEY"] = getpass.getpass("Enter your LangSmith API key: ")
os.environ["LANGSMITH_TRACING"] = "true"
```

## Instantiation

Now we can instantiate our model object and generate chat completions:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_amazon_nova import ChatAmazonNova

model = ChatAmazonNova(
    model="nova-2-lite-v1",
    temperature=0.7,
    max_tokens=2048,
    timeout=None,
    max_retries=2,
    # other params...
)
```

<Info>
  For a complete list of supported parameters and their descriptions, see the [Amazon Nova documentation](https://nova.amazon.com/dev/documentation).
</Info>

## Invocation

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
messages = [
    (
        "system",
        "You are a helpful assistant that translates English to French. Translate the user sentence.",
    ),
    ("user", "I love programming."),
]
ai_msg = model.invoke(messages)
ai_msg
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
AIMessage(content="J'adore la programmation.", response_metadata={'model': 'nova-2-lite-v1', 'finish_reason': 'stop'}, id='run-12345678-1234-1234-1234-123456789abc', usage_metadata={'input_tokens': 29, 'output_tokens': 8, 'total_tokens': 37})
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
print(ai_msg.content)
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
J'adore la programmation.
```

## Content blocks

Amazon Nova messages can contain either a single string or a list of content blocks. You can access standardized content blocks using the `content_blocks` property:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
ai_msg.content_blocks
```

Using `content_blocks` will render the content in a standard format that is consistent across other model providers. Read more about [content blocks](/oss/python/langchain/messages#standard-content-blocks).

## Streaming

Amazon Nova supports token-level streaming for real-time response generation:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
stream = model.stream_events(messages, version="v3")
for token in stream.text:
    print(token, end="", flush=True)
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
J'adore la programmation.
```

### Async streaming

For async applications, use `astream_events`:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import asyncio

async def main():
    stream = await model.astream_events(messages, version="v3")
    async for token in stream.text:
        print(token, end="", flush=True)

asyncio.run(main())
```

## Tool calling

Amazon Nova supports tool calling (function calling) on compatible models. You can check if a model supports tool calling using LangChain model profiles.

<Info>
  For details on Nova's tool calling implementation and available parameters, see the [tool calling documentation](https://nova.amazon.com/dev/documentation).
</Info>

### Basic tool usage

Bind tools to the model using Pydantic models or LangChain [`@tool`](https://reference.langchain.com/python/langchain-core/tools/convert/tool):

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from pydantic import BaseModel, Field

class GetWeather(BaseModel):
    """Get the weather for a location."""

    location: str = Field(description="City name")

model_with_tools = model.bind_tools([GetWeather])
response = model_with_tools.invoke("What's the weather in Paris?")
print(response.tool_calls)
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
[{'name': 'GetWeather', 'args': {'location': 'Paris'}, 'id': 'call_abc123', 'type': 'tool_call'}]
```

You can also access tool calls specifically in a standard format using the `tool_calls` attribute:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
response.tool_calls
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
[{'name': 'GetWeather',
  'args': {'location': 'Paris'},
  'id': 'call_abc123',
  'type': 'tool_call'}]
```

### Using LangChain tools

You can also use standard LangChain tools:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain.tools import tool

@tool
def get_weather(location: str) -> str:
    """Get the weather for a location."""
    return f"Weather in {location}: Sunny, 72°F"

model_with_tools = model.bind_tools([get_weather])
response = model_with_tools.invoke("What's the weather in San Francisco?")
```

### Controlling tool choice

Amazon Nova supports controlling when the model should use tools via the `tool_choice` parameter:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# Model decides whether to call tools (default)
model_auto = model.bind_tools([get_weather], tool_choice="auto")

# Model must call a tool
model_required = model.bind_tools([get_weather], tool_choice="required")

# Model cannot call tools
model_none = model.bind_tools([get_weather], tool_choice="none")
```

<Warning>
  **Nova's tool\_choice values**

  Amazon Nova supports `tool_choice` values of `"auto"`, `"required"`, and `"none"`. Unlike some other providers, Nova does not support `tool_choice="any"` or specifying a specific tool name as the choice value.
</Warning>

The `tool_choice="required"` option is particularly useful for ensuring the model always uses tools, such as in structured output scenarios.

## System tools

Amazon Nova provides built-in system tools that enhance the model's capabilities with integrated functionality. These tools are enabled by passing them to the model initialization or as invocation parameters.

### Available system tools

Amazon Nova supports the following built-in tools:

#### Web grounding (nova\_grounding)

The grounding tool allows the model to search the web and ground its responses with real-time information from external sources.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_amazon_nova import ChatAmazonNova

model_with_grounding = ChatAmazonNova(
    model="nova-2-lite-v1",
    system_tools=["nova_grounding"],
)

response = model_with_grounding.invoke("What are the latest developments in AI?")
```

The grounding tool will automatically search for relevant information and include citations in the response.

#### Code interpreter (nova\_code\_interpreter)

The code interpreter tool enables the model to write and execute Python code in a sandboxed environment, useful for mathematical computations, data analysis, and code generation tasks.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_amazon_nova import ChatAmazonNova

model_with_code = ChatAmazonNova(
    model="nova-2-lite-v1",
    system_tools=["nova_code_interpreter"],
)

response = model_with_code.invoke("Calculate the fibonacci sequence up to the 10th number")
```

The code interpreter executes code securely and returns both the code and its output.

### Combining system tools

You can enable multiple system tools simultaneously:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_amazon_nova import ChatAmazonNova

model_with_tools = ChatAmazonNova(
    model="nova-2-lite-v1",
    system_tools=["nova_grounding", "nova_code_interpreter"],
)

response = model_with_tools.invoke(
    "Search for the current price of Bitcoin and calculate its 7-day moving average"
)
```

The model will automatically determine which tool(s) to use based on the query.

### System tools as invocation parameters

You can also specify system tools at invocation time instead of during initialization:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_amazon_nova import ChatAmazonNova

model = ChatAmazonNova(model="nova-2-lite-v1")

# Enable grounding for this specific call
response = model.invoke(
    "What's the weather today?",
    system_tools=["nova_grounding"]
)
```

This approach is useful when you want to use different system tools for different queries with the same model instance.

<Info>
  **Tool outputs and citations**

  When using system tools, the model's response will include:

  * The main text response
  * Citations or references (for grounding tool)
  * Code execution results (for code interpreter)

  These outputs are included in the message's `response_metadata` and can be accessed for displaying sources or debugging.
</Info>

For complete details on system tools, their parameters, and capabilities, see the [Amazon Nova documentation](https://nova.amazon.com/dev/documentation).

## Structured output

Amazon Nova supports structured output through the `with_structured_output()` method, enabling you to get LLM responses in structured formats using Pydantic models or JSON schemas.

### Basic usage with Pydantic

You can constrain LLM responses to match a specific structure using Pydantic models:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from pydantic import BaseModel, Field
from langchain_amazon_nova import ChatAmazonNova

class Person(BaseModel):
    """Information about a person."""
    name: str = Field(description="The person's name")
    age: int = Field(description="The person's age")

model = ChatAmazonNova(model="nova-pro-v1")
structured_model = model.with_structured_output(Person)

result = structured_model.invoke("John is 30 years old")
print(result)
```

```output theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
Person(name='John', age=30)
```

### JSON schema support

You can also provide JSON schemas directly:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
json_schema = {
    "type": "object",
    "properties": {
        "name": {"type": "string"},
        "age": {"type": "integer"}
    },
    "required": ["name", "age"]
}

structured_model = model.with_structured_output(json_schema)
result = structured_model.invoke("Sarah is 28 years old")
print(result)
```

```output theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
{'name': 'Sarah', 'age': 28}
```

### Streaming structured output

Structured output works with streaming. The parsed object is returned once the complete response arrives:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from pydantic import BaseModel, Field

class Person(BaseModel):
    """Information about a person."""
    name: str = Field(description="The person's name")
    age: int = Field(description="The person's age")

structured_model = model.with_structured_output(Person)

for chunk in structured_model.stream("Michael is 35 years old"):
    print(chunk)
```

```output theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
Person(name='Michael', age=35)
```

### Accessing raw messages

The `include_raw` parameter allows access to both the parsed output and the raw AIMessage:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
structured_model = model.with_structured_output(Person, include_raw=True)
result = structured_model.invoke("John is 30 years old")

print(f"Parsed: {result['parsed']}")
print(f"Raw message: {result['raw']}")
```

```output theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
Parsed: Person(name='John', age=30)
Raw message: AIMessage(content='', additional_kwargs={'tool_calls': [...]}, ...)
```

This is useful for debugging, accessing metadata, or handling edge cases where parsing might fail.

### Nested and complex schemas

You can use nested Pydantic models for complex data structures:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from pydantic import BaseModel, Field
from typing import List

class Address(BaseModel):
    """A physical address."""
    street: str
    city: str
    country: str

class Person(BaseModel):
    """Information about a person."""
    name: str
    age: int
    addresses: List[Address] = Field(description="List of addresses")

structured_model = model.with_structured_output(Person)
result = structured_model.invoke(
    "John is 30 years old. He lives at 123 Main St in Seattle, USA "
    "and has a vacation home at 456 Beach Rd in Miami, USA."
)
print(result)
```

<Info>
  **Implementation details**

  Structured output uses Nova's tool calling capabilities under the hood with `tool_choice='required'` to ensure consistent structured responses. The schema is converted to a tool definition, and the tool call response is parsed back into the requested format.
</Info>

## Model profile

Amazon Nova provides different models with varying capabilities. It includes support for LangChain [model profiles](/oss/python/langchain/models#model-profiles).

<Info>
  **Model capabilities vary by model**

  Some Amazon Nova models support vision inputs while others do not. Always check model capabilities before using multimodal features.

  For a complete list of available models and their capabilities, see the [Amazon Nova documentation](https://nova.amazon.com/dev/documentation).
</Info>

## Async operations

For production applications requiring high throughput, use native async operations:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import asyncio

async def main():
    messages = [
        ("system", "You are a helpful assistant."),
        ("human", "What is the capital of France?"),
    ]
    response = await model.ainvoke(messages)
    print(response.content)

asyncio.run(main())
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
The capital of France is Paris.
```

## Chaining

Amazon Nova models work seamlessly with LangChain's LCEL (LangChain Expression Language) for building chains:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

prompt = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful assistant that translates {input_language} to {output_language}."),
    ("human", "{text}"),
])

chain = prompt | model | StrOutputParser()

result = chain.invoke({
    "input_language": "English",
    "output_language": "Spanish",
    "text": "Hello, how are you?"
})
print(result)
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
Hola, ¿cómo estás?
```

## Error handling

The model includes built-in retry logic with configurable parameters:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
model = ChatAmazonNova(
    model="nova-2-lite-v1",
    max_retries=3,  # Number of retries on failure
    timeout=60.0,   # Request timeout in seconds
)
```

For additional control over retries, use the `with_retry` method:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
model_with_custom_retry = model.with_retry(
    stop_after_attempt=5,
    wait_exponential_jitter=True,
)
```

## Troubleshooting

### Connection issues

If you encounter connection errors, verify your environment variables are set correctly:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import os
print(f"API Key set: {'NOVA_API_KEY' in os.environ}")
print(f"Base URL: {os.environ.get('NOVA_BASE_URL', 'Not set')}")
```

For authentication and connection issues, refer to the [Amazon Nova documentation](https://nova.amazon.com/dev/documentation).

### Compression errors

<Note>
  The [`ChatAmazonNova`](https://reference.langchain.com/python/langchain-amazon-nova/chat_models/ChatAmazonNova) client automatically disables compression to avoid potential decompression issues.
</Note>

If you need to customize HTTP client behavior, you can access the underlying OpenAI client:

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# The client is automatically configured with no compression
model = ChatAmazonNova(model="nova-2-lite-v1")
# model.client is the configured OpenAI client
```

### Tool calling validation errors

If you receive a validation error when binding tools, ensure the model supports tool calling.

***

## API reference

For detailed documentation of all [`ChatAmazonNova`](https://reference.langchain.com/python/langchain-amazon-nova/chat_models/ChatAmazonNova) features and configurations, head to the [`ChatAmazonNova`](https://reference.langchain.com/python/langchain-amazon-nova/chat_models/ChatAmazonNova) API reference.

For Amazon Nova-specific features, model details, and API specifications, see the [Amazon Nova documentation](https://nova.amazon.com/dev/documentation).

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/chat/amazon_nova.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
