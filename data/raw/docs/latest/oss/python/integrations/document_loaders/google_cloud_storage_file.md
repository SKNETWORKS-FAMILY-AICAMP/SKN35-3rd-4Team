> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Google cloud storage file integration

> Integrate with the Google cloud storage file document loader using LangChain Python.

> [Google Cloud Storage](https://en.wikipedia.org/wiki/Google_Cloud_Storage) is a managed service for storing unstructured data.

This covers how to load document objects from an `Google Cloud Storage (GCS) file object (blob)`.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
pip install -qU  langchain-google-community[gcs]
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_google_community import GCSFileLoader
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
loader = GCSFileLoader(project_name="aist", bucket="testing-hwc", blob="fake.docx")
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
loader.load()
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
/Users/harrisonchase/workplace/langchain/.venv/lib/python3.10/site-packages/google/auth/_default.py:83: UserWarning: Your application has authenticated using end user credentials from Google Cloud SDK without a quota project. You might receive a "quota exceeded" or "API not enabled" error. We recommend you rerun `gcloud auth application-default login` and make sure a quota project is added. Or you can use service accounts instead. For more information about service accounts, see https://cloud.google.com/docs/authentication/
  warnings.warn(_CLOUD_SDK_CREDENTIALS_WARNING)
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
[Document(page_content='Lorem ipsum dolor sit amet.', lookup_str='', metadata={'source': '/var/folders/y6/8_bzdg295ld6s1_97_12m4lr0000gn/T/tmp3srlf8n8/fake.docx'}, lookup_index=0)]
```

If you want to use an alternative loader, you can provide a custom function, for example:

<Warning>
  The `langchain-community` package is no longer maintained. Examples that import from `langchain_community` may be outdated or broken. Use with caution.
</Warning>

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_community.document_loaders import PyPDFLoader


def load_pdf(file_path):
    return PyPDFLoader(file_path)


loader = GCSFileLoader(
    project_name="aist", bucket="testing-hwc", blob="fake.pdf", loader_func=load_pdf
)
```

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/document_loaders/google_cloud_storage_file.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
