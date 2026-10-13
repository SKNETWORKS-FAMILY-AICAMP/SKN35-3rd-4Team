> ## Documentation Index
> Fetch the complete documentation index at: https://docs.langchain.com/llms.txt
> Use this file to discover all available pages before exploring further.

# Document loader integrations

> Integrate with document loaders using LangChain Python.

Document loaders provide a **standard interface** for reading data from different sources (such as Slack, Notion, or Google Drive) into LangChain’s [Document](https://reference.langchain.com/python/langchain-core/documents/base/Document) format.
This ensures that data can be handled consistently regardless of the source.

All document loaders implement the [`BaseLoader`](https://reference.langchain.com/python/langchain-core/document_loaders/base/BaseLoader) interface.

<Warning>
  Community document loaders are user-contributed and unverified. LangChain does not review or endorse these integrations; use them at your own risk.
</Warning>

## Interface

Each document loader may define its own parameters, but they share a common API:

* `load()`: Loads all documents at once.
* `lazy_load()`: Streams documents lazily, useful for large datasets.

```python theme={"theme":{"light":"catppuccin-latte","dark":"catppuccin-mocha"}}
from langchain_docling.loader import DoclingLoader

FILE_PATH = "https://arxiv.org/pdf/2408.09869"

loader = DoclingLoader(file_path=FILE_PATH)

# Load all documents
documents = loader.load()

# For large datasets, lazily load documents
for document in loader.lazy_load():
    print(document)
```

## By category

### Productivity tools

The below document loaders allow you to load data from commonly used productivity tools.

| Document Loader | API reference |
| - | - |
| [AgentMail](https://github.com/agentmail-to/langchain-agentmail) | [`AgentMailLoader`](https://github.com/agentmail-to/langchain-agentmail) |
| [Google Classroom](/oss/python/integrations/document_loaders/google_classroom) | [`GoogleClassroomLoader`](https://pypi.org/project/langchain-google-classroom/) |

### Webpages

The below document loaders allow you to load webpages.

| Document Loader | Description | Package/API |
| - | - | - |
| [Unstructured](/oss/python/integrations/document_loaders/unstructured_file) | Uses Unstructured to load and parse web pages | Package |
| [Apify Dataset](https://docs.apify.com/integrations/langchain) | Load documents from Apify datasets | API |
| [Apify Crawl](https://docs.apify.com/integrations/langchain) | Crawl a website on demand and load each page as a Document | API |
| [Diffbot Crawl Loader](https://github.com/diffbot/langchain-diffbot) | Crawl a website and load each page as ontologically consistent JSON using the Diffbot Crawl API | API |
| [Diffbot Extract Loader](https://github.com/diffbot/langchain-diffbot) | Load web pages as ontologically consistent JSON using the Diffbot Extract API | API |
| [Docling](/oss/python/integrations/document_loaders/docling) | Uses Docling to load and parse web pages | Package |
| [DomPruner](https://github.com/dong7812/dompruner-py) | DOM AST pruning: loads web pages as compact Markdown with 97%+ token reduction, no API key | Package |
| [Firecrawl](https://docs.firecrawl.dev) | Turns websites into clean, LLM-ready data via scrape/crawl/map/extract/search | API |
| [Hyperbrowser](https://docs.hyperbrowser.ai) | Platform for running and scaling headless browsers, can be used to scrape/crawl any site | API |
| [OpeddFeedLoader](https://opedd.com/for-ai-agents) | Load a licensed Opedd content catalog as Documents with licensing provenance | API |
| [ProxyHatLoader](https://docs.proxyhat.com) | Load web pages through ProxyHat residential proxies as Documents | API |
| [AgentQL](https://docs.agentql.com/) | Web interaction and structured data extraction from any web page using an AgentQL query or a Natural Language prompt | API |
| [CRW](https://fastcrw.com) | Open-source Firecrawl-compatible web scraper via local binary or fastcrw\.com cloud | Package |
| [Plasmate](https://docs.plasmate.app/integration-langchain) | Agent-native headless browser with Set of Mark (SOM) structured UI extraction | Package |
| [Spidra](https://docs.spidra.io) | AI-powered web scraper with real browsers, CAPTCHA solving, and structured data extraction | API |

### PDFs

Partner and community loaders for PDF files. Hosted partner guides are listed first. Classic loaders from [`langchain-community`](https://pypi.org/project/langchain-community/) and other community packages follow. For the full download-sorted catalog, see [All document loaders](#all-document-loaders).

| Document Loader | Description | Package/API |
| - | - | - |
| [Unstructured](/oss/python/integrations/document_loaders/unstructured_file) | Uses Unstructured's open source library to load PDFs | Package |
| [Upstage Document Parse Loader](/oss/python/integrations/document_loaders/upstage) | Load PDF files using UpstageDocumentParseLoader | Package |
| [Docling](/oss/python/integrations/document_loaders/docling) | Load PDF files using Docling | Package |
| [`PyPDFLoader`](https://python.langchain.com/api_reference/community/document_loaders/langchain_community.document_loaders.pdf.PyPDFLoader.html) | Load PDF files with `pypdf` (`langchain-community`) | Community |
| [`PyMuPDFLoader`](https://python.langchain.com/api_reference/community/document_loaders/langchain_community.document_loaders.pdf.PyMuPDFLoader.html) | Load PDF files with PyMuPDF (`langchain-community`) | Community |
| [`PDFMinerLoader`](https://python.langchain.com/api_reference/community/document_loaders/langchain_community.document_loaders.pdf.PDFMinerLoader.html) | Load PDF files with PDFMiner (`langchain-community`) | Community |
| [`PDFPlumberLoader`](https://python.langchain.com/api_reference/community/document_loaders/langchain_community.document_loaders.pdf.PDFPlumberLoader.html) | Load PDF files with pdfplumber (`langchain-community`) | Community |
| [MinerU](https://mineru.net) | Load PDF and other documents using MinerU | Package |
| [UnDatasIO](https://undatas.io) | Load PDF files using UnDatasIO | Package |
| [OpenDataLoader PDF](https://github.com/opendataloader-project/langchain-opendataloader-pdf) | Load PDF files using OpenDataLoader PDF | Package |
| [CVFileLoader](https://cvfile.org) | Load .cv PDF/A-3u files with embedded Markdown, HTML, and JSON Resume payloads | Package |
| [pdfmuse](https://github.com/casperkwok/pdfmuse) | Load PDF and DOCX files deterministically, with exact coordinates, tables and per-block section metadata for RAG | Package |
| [oxidize-pdf](https://github.com/bzsanti/oxidize-pdf-integrations/tree/main/langchain) | Load PDF files using a Rust engine with element-disjoint RAG chunking | Package |
| [pdf-inspector](https://github.com/undacmic/langchain-pdf-inspector) | Load PDF files using pdf-inspector | Package |

### Cloud providers

The below document loaders allow you to load documents from your favorite cloud providers.

| Document Loader | Description | Partner Package | API reference / Source |
| - | - | - | - |
| [Azure Blob Storage](/oss/python/integrations/document_loaders/azure_blob_storage) | Load documents from Azure Blob Storage containers or individual blobs | ✅ | [`langchain-ai/langchain-azure`](https://github.com/langchain-ai/langchain-azure/tree/main/libs/azure-storage) |
| [Google Cloud Storage Directory](/oss/python/integrations/document_loaders/google_cloud_storage_directory) | Load documents from GCS bucket | ✅ | [`GCSDirectoryLoader`](https://reference.langchain.com/python/langchain-google-community/gcs_directory/GCSDirectoryLoader) |
| [Google Cloud Storage File](/oss/python/integrations/document_loaders/google_cloud_storage_file) | Load documents from GCS file object | ✅ | [`GCSFileLoader`](https://reference.langchain.com/python/langchain-google-community/gcs_file/GCSFileLoader) |
| [Google Drive](/oss/python/integrations/document_loaders/google_drive) | Load documents from Google Drive (Google Docs only) | ✅ | [`GoogleDriveLoader`](https://reference.langchain.com/python/langchain-google-community/drive/GoogleDriveLoader) |

### Common file types

The below document loaders allow you to load data from common data formats.

| Document Loader | Data Type |
| - | - |
| [`Unstructured`](/oss/python/integrations/document_loaders/unstructured_file) | Many file types (see [https://docs.unstructured.io/platform/supported-file-types](https://docs.unstructured.io/platform/supported-file-types)) |
| [`HwpHwpxLoader`](https://github.com/jaypakdevkr/HWP-Loader) | HWP/HWPX files |
| [`DoclingLoader`](/oss/python/integrations/document_loaders/docling) | Various file types (see [https://docling-project.github.io/docling/](https://docling-project.github.io/docling/)) |
| [`PolarisAIDataInsightLoader`](https://datainsight.polarisoffice.com/playground) | Various file types (see [https://datainsight.polarisoffice.com/documentation?docType=doc\_extract](https://datainsight.polarisoffice.com/documentation?docType=doc_extract)) |

## All document loaders

<div class="integration-downloads-table">
  | Integration | Downloads |
  | :- | :- |
  | [`Google bigquery`](/oss/python/integrations/document_loaders/google_bigquery) | <span data-sort-value="11000000"><a href="https://pypi.org/project/langchain-google-community/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-community/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google cloud storage directory`](/oss/python/integrations/document_loaders/google_cloud_storage_directory) | <span data-sort-value="11000000"><a href="https://pypi.org/project/langchain-google-community/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-community/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google cloud storage file`](/oss/python/integrations/document_loaders/google_cloud_storage_file) | <span data-sort-value="11000000"><a href="https://pypi.org/project/langchain-google-community/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-community/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google drive`](/oss/python/integrations/document_loaders/google_drive) | <span data-sort-value="11000000"><a href="https://pypi.org/project/langchain-google-community/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-community/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google speech-to-text audio transcripts`](/oss/python/integrations/document_loaders/google_speech_to_text) | <span data-sort-value="11000000"><a href="https://pypi.org/project/langchain-google-community/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-community/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Oracle AI vector search document processing`](/oss/python/integrations/document_loaders/oracleai) | <span data-sort-value="230000"><a href="https://pypi.org/project/langchain-oracledb/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-oracledb/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Oracle autonomous database`](/oss/python/integrations/document_loaders/oracleadb_loader) | <span data-sort-value="230000"><a href="https://pypi.org/project/langchain-oracledb/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-oracledb/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`AstraDB`](/oss/python/integrations/document_loaders/astradb) | <span data-sort-value="174000"><a href="https://pypi.org/project/langchain-astradb/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-astradb/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`UnstructuredLoader`](/oss/python/integrations/document_loaders/unstructured_file) | <span data-sort-value="172000"><a href="https://pypi.org/project/langchain-unstructured/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-unstructured/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Docling`](/oss/python/integrations/document_loaders/docling) | <span data-sort-value="79000"><a href="https://pypi.org/project/langchain-docling/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-docling/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`PyMuPDF4LLMLoader`](https://github.com/pymupdf/langchain-pymupdf4llm) | <span data-sort-value="49000"><a href="https://pypi.org/project/langchain-pymupdf4llm/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-pymupdf4llm/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Upstage`](/oss/python/integrations/document_loaders/upstage) | <span data-sort-value="37000"><a href="https://pypi.org/project/langchain-upstage/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-upstage/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google alloydb for postgresql`](/oss/python/integrations/document_loaders/google_alloydb) | <span data-sort-value="34000"><a href="https://pypi.org/project/langchain-google-alloydb-pg/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-alloydb-pg/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google firestore (native mode)`](/oss/python/integrations/document_loaders/google_firestore) | <span data-sort-value="29000"><a href="https://pypi.org/project/langchain-google-firestore/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-firestore/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`ApifyCrawlLoader`](https://docs.apify.com/integrations/langchain) | <span data-sort-value="23000"><a href="https://pypi.org/project/langchain-apify/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-apify/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`ApifyDatasetLoader`](https://docs.apify.com/integrations/langchain) | <span data-sort-value="23000"><a href="https://pypi.org/project/langchain-apify/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-apify/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google cloud SQL for postgresql`](https://docs.cloud.google.com/sql/docs/postgres) | <span data-sort-value="22000"><a href="https://pypi.org/project/langchain-google-cloud-sql-pg/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-cloud-sql-pg/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google spanner`](/oss/python/integrations/document_loaders/google_spanner) | <span data-sort-value="22000"><a href="https://pypi.org/project/langchain-google-spanner/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-spanner/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`DomPrunerLoader`](https://github.com/dong7812/dompruner-py) | <span data-sort-value="4000"><a href="https://pypi.org/project/dompruner/" target="_blank">  <img src="https://static.pepy.tech/badge/dompruner/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`OpenDataLoader PDF`](https://github.com/opendataloader-project/langchain-opendataloader-pdf) | <span data-sort-value="3000"><a href="https://pypi.org/project/langchain-opendataloader-pdf/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-opendataloader-pdf/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Docugami`](/oss/python/integrations/document_loaders/docugami) | <span data-sort-value="2000"><a href="https://pypi.org/project/docugami-langchain/" target="_blank">  <img src="https://static.pepy.tech/badge/docugami-langchain/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`YoutubeLoaderDL`](https://github.com/aqib0770/langchain-yt-dlp) | <span data-sort-value="2000"><a href="https://pypi.org/project/langchain-yt-dlp/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-yt-dlp/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Azure blob storage loader`](/oss/python/integrations/document_loaders/azure_blob_storage) | <span data-sort-value="1000"><a href="https://pypi.org/project/langchain-azure-storage/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-azure-storage/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`PDFParser`](https://dev.writer.com/api-reference/tool-api/pdf-parser#parse-pdf) | <span data-sort-value="1000"><a href="https://pypi.org/project/langchain-writer/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-writer/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`SingleStoreLoader`](https://github.com/singlestore-labs/langchain-singlestore/) | <span data-sort-value="1000"><a href="https://pypi.org/project/langchain-singlestore/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-singlestore/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`FlatmarkLoader`](https://github.com/flatmark-dev/flatmark-integrations/blob/main/langchain/README.md) | <span data-sort-value="958"><a href="https://pypi.org/project/langchain-flatmark/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-flatmark/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`CapslaneLoader`](https://capslane.com/integrations/langchain) | <span data-sort-value="936"><a href="https://pypi.org/project/capslane/" target="_blank">  <img src="https://static.pepy.tech/badge/capslane/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`SecureLangChainLoader`](https://github.com/arsbr/Veritensor) | <span data-sort-value="807"><a href="https://pypi.org/project/veritensor/" target="_blank">  <img src="https://static.pepy.tech/badge/veritensor/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`SpidraLoader`](https://docs.spidra.io) | <span data-sort-value="772"><a href="https://pypi.org/project/langchain-spidra/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-spidra/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`AlfrescoLoader`](https://github.com/OpenDMA/langchain-opendma/blob/main/docs/Loader.md#alfrescoloader) | <span data-sort-value="725"><a href="https://pypi.org/project/langchain-opendma/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-opendma/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`OpenDMALoader`](https://github.com/OpenDMA/langchain-opendma/blob/main/docs/Loader.md) | <span data-sort-value="725"><a href="https://pypi.org/project/langchain-opendma/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-opendma/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`MinerULoader`](https://mineru.net) | <span data-sort-value="674"><a href="https://pypi.org/project/langchain-mineru/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-mineru/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`HydrafetchLoader`](https://docs.hydrafetch.com) | <span data-sort-value="595"><a href="https://pypi.org/project/langchain-hydrafetch/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-hydrafetch/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`LyrenthLoader`](https://lyrenth.com/docs/integrations) | <span data-sort-value="571"><a href="https://pypi.org/project/langchain-lyrenth/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-lyrenth/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`CrwLoader`](https://fastcrw.com) | <span data-sort-value="563"><a href="https://pypi.org/project/langchain-crw/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-crw/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google memorystore for Redis`](/oss/python/integrations/document_loaders/google_memorystore_redis) | <span data-sort-value="534"><a href="https://pypi.org/project/langchain-google-memorystore-redis/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-memorystore-redis/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`XNSBlobLoader`](https://docs.xns.tech) | <span data-sort-value="491"><a href="https://pypi.org/project/langchain-xns/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-xns/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`XNSLoader`](https://docs.xns.tech) | <span data-sort-value="491"><a href="https://pypi.org/project/langchain-xns/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-xns/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`QuanticDataLoader`](https://quanticdata.io/docs/) | <span data-sort-value="476"><a href="https://pypi.org/project/langchain-quanticdata/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-quanticdata/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google bigtable`](/oss/python/integrations/document_loaders/google_bigtable) | <span data-sort-value="451"><a href="https://pypi.org/project/langchain-google-bigtable/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-bigtable/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`HyperbrowserLoader`](https://www.hyperbrowser.ai/docs/home) | <span data-sort-value="450"><a href="https://pypi.org/project/langchain-hyperbrowser/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-hyperbrowser/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`PowerScaleDocumentLoader`](/oss/python/integrations/document_loaders/powerscale) | <span data-sort-value="447"><a href="https://pypi.org/project/powerscale-rag-connector/" target="_blank">  <img src="https://static.pepy.tech/badge/powerscale-rag-connector/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`FirecrawlLoader`](https://docs.firecrawl.dev) | <span data-sort-value="417"><a href="https://pypi.org/project/langchain-firecrawl/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-firecrawl/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`PaddleOCR-VL`](https://www.paddleocr.com) | <span data-sort-value="382"><a href="https://pypi.org/project/langchain-paddleocr/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-paddleocr/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`PdfInspectorLoader`](https://github.com/undacmic/langchain-pdf-inspector) | <span data-sort-value="379"><a href="https://pypi.org/project/langchain-pdf-inspector/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-pdf-inspector/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`langchain_box`](https://developer.box.com/) | <span data-sort-value="370"><a href="https://pypi.org/project/langchain-box/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-box/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`PolarisAIDataInsightLoader`](https://datainsight.polarisoffice.com/playground) | <span data-sort-value="363"><a href="https://pypi.org/project/langchain-polaris-ai-datainsight/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-polaris-ai-datainsight/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Outline`](https://github.com/10Pines/langchain-outline) | <span data-sort-value="355"><a href="https://pypi.org/project/langchain-outline/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-outline/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`ReplyLayerLoader`](https://replylayer.ai/docs/guides/langchain) | <span data-sort-value="331"><a href="https://pypi.org/project/langchain-replylayer/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-replylayer/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`OpeddFeedLoader`](https://opedd.com/for-ai-agents) | <span data-sort-value="301"><a href="https://pypi.org/project/langchain-opedd/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-opedd/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google Classroom`](/oss/python/integrations/document_loaders/google_classroom) | <span data-sort-value="254"><a href="https://pypi.org/project/langchain-google-classroom/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-classroom/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google cloud SQL for mysql`](/oss/python/integrations/document_loaders/google_cloud_sql_mysql) | <span data-sort-value="254"><a href="https://pypi.org/project/langchain-google-cloud-sql-mysql/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-cloud-sql-mysql/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Kinetica document loader`](https://github.com/kineticadb/langchain-kinetica) | <span data-sort-value="242"><a href="https://pypi.org/project/langchain-kinetica/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-kinetica/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`AnakinLoader`](https://anakin.io/docs/documentation) | <span data-sort-value="239"><a href="https://pypi.org/project/langchain-anakin/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-anakin/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google firestore in datastore mode`](/oss/python/integrations/document_loaders/google_datastore) | <span data-sort-value="237"><a href="https://pypi.org/project/langchain-google-datastore/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-datastore/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`PdfmuseLoader`](https://github.com/casperkwok/pdfmuse) | <span data-sort-value="234"><a href="https://pypi.org/project/langchain-pdfmuse/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-pdfmuse/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`HwpHwpxLoader`](https://github.com/jaypakdevkr/HWP-Loader) | <span data-sort-value="224"><a href="https://pypi.org/project/langchain-hwp-hwpx-loader/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-hwp-hwpx-loader/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`CVFileLoader`](https://cvfile.org) | <span data-sort-value="220"><a href="https://pypi.org/project/langchain-cvfile/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-cvfile/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`ProxyHatLoader`](https://docs.proxyhat.com) | <span data-sort-value="220"><a href="https://pypi.org/project/langchain-proxyhat/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-proxyhat/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`AirbyteLoader`](https://docs.airbyte.com/integrations/) | <span data-sort-value="212"><a href="https://pypi.org/project/langchain-airbyte/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-airbyte/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`DiffbotCrawlLoader`](https://github.com/diffbot/langchain-diffbot) | <span data-sort-value="211"><a href="https://pypi.org/project/langchain-diffbot/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-diffbot/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`DiffbotExtractLoader`](https://github.com/diffbot/langchain-diffbot) | <span data-sort-value="211"><a href="https://pypi.org/project/langchain-diffbot/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-diffbot/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google cloud SQL for SQL server`](/oss/python/integrations/document_loaders/google_cloud_sql_mssql) | <span data-sort-value="209"><a href="https://pypi.org/project/langchain-google-cloud-sql-mssql/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-cloud-sql-mssql/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`AgentQLLoader`](https://docs.agentql.com/home) | <span data-sort-value="203"><a href="https://pypi.org/project/langchain-agentql/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-agentql/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Google el carro for Oracle workloads`](https://github.com/googleapis/langchain-google-el-carro-python/) | <span data-sort-value="175"><a href="https://pypi.org/project/langchain-google-el-carro/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-google-el-carro/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`PlasmateSOMLLoader`](https://docs.plasmate.app/integration-langchain) | <span data-sort-value="168"><a href="https://pypi.org/project/langchain-plasmate/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-plasmate/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Undatasio`](https://undatas.io) | <span data-sort-value="161"><a href="https://pypi.org/project/langchain-undatasio/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-undatasio/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`Soniox`](https://soniox.com/docs/stt/concepts/supported-languages) | <span data-sort-value="160"><a href="https://pypi.org/project/langchain-soniox/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-soniox/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`AgentMail`](https://github.com/agentmail-to/langchain-agentmail) | <span data-sort-value="144"><a href="https://pypi.org/project/langchain-agentmail/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-agentmail/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`OxidizePdfLoader`](https://github.com/bzsanti/oxidize-pdf-integrations/tree/main/langchain) | <span data-sort-value="129"><a href="https://pypi.org/project/langchain-oxidize-pdf/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-oxidize-pdf/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`EnconvertLoader`](https://github.com/enconvert/langchain-enconvert) | <span data-sort-value="122"><a href="https://pypi.org/project/langchain-enconvert/" target="_blank">  <img src="https://static.pepy.tech/badge/langchain-enconvert/month" alt="Downloads per month" noZoom class="rounded not-prose" /></a></span> |
  | [`LangSmithLoader`](/oss/python/integrations/document_loaders/langsmith) | <span data-sort-value="-1">N/A</span> |
</div>

***

<div className="source-links">
  <Callout icon="terminal-2">
    [Connect these docs](/use-these-docs) to your agent of choice via MCP for real-time answers.
  </Callout>

  <Callout icon="edit">
    [Edit this page on GitHub](https://github.com/langchain-ai/docs/edit/main/src/oss/python/integrations/document_loaders/index.mdx) or [file an issue](https://github.com/langchain-ai/docs/issues/new/choose).
  </Callout>
</div>
