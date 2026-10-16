> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Google cloud text-to-speech integration

> Integrate with the Google cloud text-to-speech tool using LangChain Python.

> [Google Cloud Text-to-Speech](https://cloud.google.com/text-to-speech) enables developers to synthesize natural-sounding speech with 100+ voices, available in multiple languages and variants. It applies DeepMind’s groundbreaking research in WaveNet and Google’s powerful neural networks to deliver the highest fidelity possible.
>
> It supports multiple languages, including English, German, Polish, Spanish, Italian, French, Portuguese, and Hindi.

This notebook shows how to interact with the `Google Cloud Text-to-Speech API` to achieve speech synthesis capabilities.

First, you need to set up a Google Cloud project. You can follow the [Google Cloud Text-to-Speech setup instructions](https://cloud.google.com/text-to-speech/docs/before-you-begin).

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
!pip install -U langchain-google-community[texttospeech]
```

## Instantiation

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_google_community import TextToSpeechTool
```

## Deprecated GoogleCloudTextToSpeechTool

<Warning>
  The `langchain-community` package is no longer maintained. Examples that import from `langchain_community` may be outdated or broken. Use with caution.
</Warning>

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_community.tools import GoogleCloudTextToSpeechTool
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
text_to_speak = "Hello world!"

tts = GoogleCloudTextToSpeechTool()
tts.name
```

We can generate audio, save it to the temporary file and then play it.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
speech_file = tts.run(text_to_speak)
```

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/tools/google_cloud_texttospeech.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
