from pathlib import Path
import os

import chromadb
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[3]
CHUNKS_PATH = ROOT / "data" / "processed" / "chunks.jsonl"
ENV_PATH = ROOT / ".env"

COLLECTION_NAME = "langchain_migration"
EMBEDDING_MODEL = "text-embedding-3-small"
EMBEDDING_DIMENSIONS = 1536
DISTANCE = "cosine"

ADD_BATCH_SIZE = 300
MAX_RETRIES = 5

def cloud_client() -> chromadb.CloudClient:
    load_dotenv(ENV_PATH)
    return chromadb.CloudClient(
        api_key=os.environ.get("CHROMA_API_KEY"),
        tenant=os.environ.get("CHROMA_TENANT"),
        database=os.environ.get("CHROMA_DATABASE"),
    )