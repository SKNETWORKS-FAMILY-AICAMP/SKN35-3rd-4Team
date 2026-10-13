> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Google cloud storage directory integration

> Integrate with the Google cloud storage directory document loader using LangChain Python.

> [Google Cloud Storage](https://en.wikipedia.org/wiki/Google_Cloud_Storage) is a managed service for storing unstructured data.

This covers how to load document objects from an `Google Cloud Storage (GCS) directory (bucket)`.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
pip install -qU  langchain-google-community[gcs]
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_google_community import GCSDirectoryLoader
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
loader = GCSDirectoryLoader(project_name="aist", bucket="testing-hwc")
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
loader.load()
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
/Users/harrisonchase/workplace/langchain/.venv/lib/python3.10/site-packages/google/auth/_default.py:83: UserWarning: Your application has authenticated using end user credentials from Google Cloud SDK without a quota project. You might receive a "quota exceeded" or "API not enabled" error. We recommend you rerun `gcloud auth application-default login` and make sure a quota project is added. Or you can use service accounts instead. For more information about service accounts, see https://cloud.google.com/docs/authentication/
  warnings.warn(_CLOUD_SDK_CREDENTIALS_WARNING)
/Users/harrisonchase/workplace/langchain/.venv/lib/python3.10/site-packages/google/auth/_default.py:83: UserWarning: Your application has authenticated using end user credentials from Google Cloud SDK without a quota project. You might receive a "quota exceeded" or "API not enabled" error. We recommend you rerun `gcloud auth application-default login` and make sure a quota project is added. Or you can use service accounts instead. For more information about service accounts, see https://cloud.google.com/docs/authentication/
  warnings.warn(_CLOUD_SDK_CREDENTIALS_WARNING)
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
[Document(page_content='Lorem ipsum dolor sit amet.', lookup_str='', metadata={'source': '/var/folders/y6/8_bzdg295ld6s1_97_12m4lr0000gn/T/tmpz37njh7u/fake.docx'}, lookup_index=0)]
```

## Specifying a prefix

You can also specify a prefix for more fine-grained control over what files to load -including loading all files from a specific folder-.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
loader = GCSDirectoryLoader(project_name="aist", bucket="testing-hwc", prefix="fake")
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
loader.load()
```

```text theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
/Users/harrisonchase/workplace/langchain/.venv/lib/python3.10/site-packages/google/auth/_default.py:83: UserWarning: Your application has authenticated using end user credentials from Google Cloud SDK without a quota project. You might receive a "quota exceeded" or "API not enabled" error. We recommend you rerun `gcloud auth application-default login` and make sure a quota project is added. Or you can use service accounts instead. For more information about service accounts, see https://cloud.google.com/docs/authentication/
  warnings.warn(_CLOUD_SDK_CREDENTIALS_WARNING)
/Users/harrisonchase/workplace/langchain/.venv/lib/python3.10/site-packages/google/auth/_default.py:83: UserWarning: Your application has authenticated using end user credentials from Google Cloud SDK without a quota project. You might receive a "quota exceeded" or "API not enabled" error. We recommend you rerun `gcloud auth application-default login` and make sure a quota project is added. Or you can use service accounts instead. For more information about service accounts, see https://cloud.google.com/docs/authentication/
  warnings.warn(_CLOUD_SDK_CREDENTIALS_WARNING)
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
[Document(page_content='Lorem ipsum dolor sit amet.', lookup_str='', metadata={'source': '/var/folders/y6/8_bzdg295ld6s1_97_12m4lr0000gn/T/tmpylg6291i/fake.docx'}, lookup_index=0)]
```

## Continue on failure to load a single file

Files in a GCS bucket may cause errors during processing. Enable the `continue_on_failure=True` argument to allow silent failure. This means failure to process a single file will not break the function, it will log a warning instead.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
loader = GCSDirectoryLoader(
    project_name="aist", bucket="testing-hwc", continue_on_failure=True
)
```

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
loader.load()
```

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/document_loaders/google_cloud_storage_directory.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
