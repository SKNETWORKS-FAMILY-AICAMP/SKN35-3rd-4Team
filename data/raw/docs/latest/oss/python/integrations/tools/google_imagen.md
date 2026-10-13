> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Google imagen integration

> Integrate with the Google imagen tool using LangChain Python.

> [Imagen on Gemini Enterprise Agent Platform](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/image/overview) brings Google's state of the art image generative AI capabilities to application developers. With Imagen on Gemini Enterprise Agent Platform, application developers can build next-generation AI products that transform their user's imagination into high quality visual assets using AI generation, in seconds.

With Imagen on LangChain , You can do the following tasks

* [VertexAIImageGeneratorChat](#image-generation) : Generate novel images using only a text prompt (text-to-image AI generation).
* [VertexAIImageEditorChat](#image-editing) : Edit an entire uploaded or generated image with a text prompt.
* [VertexAIImageCaptioning](#image-captioning) : Get text descriptions of images with visual captioning.
* [VertexAIVisualQnAChat](#visual-question-answering-vqa) : Get answers to a question about an image with Visual Question Answering (VQA).
  * NOTE : Currently we support only single-turn chat for Visual QnA (VQA)

## Image generation

Generate novel images using only a text prompt (text-to-image AI generation)

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain.messages import AIMessage, HumanMessage
from langchain_google_vertexai.vision_models import VertexAIImageGeneratorChat
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# Create Image Generation model Object
generator = VertexAIImageGeneratorChat()
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
messages = [HumanMessage(content=["a cat at the beach"])]
response = generator.invoke(messages)
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# To view the generated Image
generated_image = response.content[0]
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import base64
import io

from PIL import Image

# Parse response object to get base64 string for image
img_base64 = generated_image["image_url"]["url"].split(",")[-1]

# Convert base64 string to Image
img = Image.open(io.BytesIO(base64.decodebytes(bytes(img_base64, "utf-8"))))

# view Image
img
```

<p>
  <img src="https://mintcdn.com/langchain-5e9cc07a/x_qjL89cw5RbZp-3/images/integrations/imagen-generated-cat.jpg?fit=max&auto=format&n=x_qjL89cw5RbZp-3&q=85&s=7fd0bbd447c38e106e79e99fcd76a578" width="1024" height="1024" data-path="images/integrations/imagen-generated-cat.jpg" />
</p>

## Image editing

Edit an entire uploaded or generated image with a text prompt.

### Edit generated image

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain.messages import AIMessage, HumanMessage
from langchain_google_vertexai.vision_models import (
    VertexAIImageEditorChat,
    VertexAIImageGeneratorChat,
)
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# Create Image Generation model Object
generator = VertexAIImageGeneratorChat()

# Provide a text input for image
messages = [HumanMessage(content=["a cat at the beach"])]

# call the model to generate an image
response = generator.invoke(messages)

# read the image object from the response
generated_image = response.content[0]
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# Create Image Editor model Object
editor = VertexAIImageEditorChat()
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# Write prompt for editing and pass the "generated_image"
messages = [HumanMessage(content=[generated_image, "a dog at the beach "])]

# Call the model for editing Image
editor_response = editor.invoke(messages)
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
import base64
import io

from PIL import Image

# Parse response object to get base64 string for image
edited_img_base64 = editor_response.content[0]["image_url"]["url"].split(",")[-1]

# Convert base64 string to Image
edited_img = Image.open(
    io.BytesIO(base64.decodebytes(bytes(edited_img_base64, "utf-8")))
)

# view Image
edited_img
```

<p>
  <img src="https://mintcdn.com/langchain-5e9cc07a/x_qjL89cw5RbZp-3/images/integrations/imagen-edited-cat.jpg?fit=max&auto=format&n=x_qjL89cw5RbZp-3&q=85&s=89c508316ed96bc5e6c2d6874cb37d4f" width="1024" height="1024" data-path="images/integrations/imagen-edited-cat.jpg" />
</p>

## Image captioning

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_google_vertexai import VertexAIImageCaptioning

# Initialize the Image Captioning Object
model = VertexAIImageCaptioning()
```

NOTE :  we're using generated image in [Image Generation Section](#image-generation)

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
# use image generated in Image Generation Section
img_base64 = generated_image["image_url"]["url"]
response = model.invoke(img_base64)
print(f"Generated Caption : {response}")

# Convert base64 string to Image
img = Image.open(
    io.BytesIO(base64.decodebytes(bytes(img_base64.split(",")[-1], "utf-8")))
)

# display Image
img
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
Generated Cpation : a cat sitting on the beach looking at the camera
```

<p>
  <img src="https://mintcdn.com/langchain-5e9cc07a/x_qjL89cw5RbZp-3/images/integrations/imagen-cat-beach.jpg?fit=max&auto=format&n=x_qjL89cw5RbZp-3&q=85&s=620689fa3c5ef5af4aeffd79d7a34f8d" width="1024" height="1024" data-path="images/integrations/imagen-cat-beach.jpg" />
</p>

## Visual question answering (VQA)

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_google_vertexai import VertexAIVisualQnAChat

model = VertexAIVisualQnAChat()
```

NOTE :  we're using generated image in [Image Generation Section](#image-generation)

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
question = "What animal is shown in the image?"
response = model.invoke(
    input=[
        HumanMessage(
            content=[
                {"type": "image_url", "image_url": {"url": img_base64}},
                question,
            ]
        )
    ]
)

print(f"question : {question}\nanswer : {response.content}")

# Convert base64 string to Image
img = Image.open(
    io.BytesIO(base64.decodebytes(bytes(img_base64.split(",")[-1], "utf-8")))
)

# display Image
img
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
question : What animal is shown in the image?
answer : cat
```

<p>
  <img src="https://mintcdn.com/langchain-5e9cc07a/x_qjL89cw5RbZp-3/images/integrations/imagen-cat-beach.jpg?fit=max&auto=format&n=x_qjL89cw5RbZp-3&q=85&s=620689fa3c5ef5af4aeffd79d7a34f8d" width="1024" height="1024" data-path="images/integrations/imagen-cat-beach.jpg" />
</p>

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/tools/google_imagen.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
