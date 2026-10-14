import hashlib
import json
import sys
import time

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_openai import OpenAIEmbeddings

from . import (
    ADD_BATCH_SIZE, CHUNKS_PATH, COLLECTION_NAME, DISTANCE, EMBEDDING_DIMENSIONS, EMBEDDING_MODEL,
    ENV_PATH, MAX_RETRIES, ROOT, cloud_client,
)

METADATA_FIELDS = [
    "source", "era", "url", "path", "title", "section", "doc_section", "group",
    "old", "new", "kind", "import_status", "seen_in", "imports", "packages", "has_code", "chars",
    "class", "method", "status_1x", "doc_refs",
]
SMOKE_QUERIES = [
    "from langchain.chains import LLMChain",
    "from langchain.chat_models import ChatOpenAI",
    "ConversationBufferMemory replacement",
    "initialize_agent AgentExecutor create_agent",
]

import os
import chromadb
from langchain_chroma import Chroma

def text_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def to_metadata(chunk: dict) -> dict:
    meta = {}
    for key in METADATA_FIELDS:
        value = chunk.get(key)
        if value is None:
            continue
        if isinstance(value, list):
            value = ", ".join(value)
        meta[key] = value
    meta["text_hash"] = text_hash(chunk["text"])
    return meta


def open_store() -> Chroma:
    load_dotenv(ENV_PATH)
    embeddings = OpenAIEmbeddings(model=EMBEDDING_MODEL, dimensions=EMBEDDING_DIMENSIONS)
    store = Chroma(
        collection_name=COLLECTION_NAME,
        embedding_function=embeddings,
        client=cloud_client(),
        collection_metadata={
            "hnsw:space": DISTANCE,
            "embedding_model": EMBEDDING_MODEL,
            "embedding_dimensions": EMBEDDING_DIMENSIONS,
        },
    )
    # 다른 모델로 만든 벡터와 섞이지 않도록 확인
    stored = store._collection.metadata or {}
    if stored.get("embedding_model", EMBEDDING_MODEL) != EMBEDDING_MODEL or \
            stored.get("embedding_dimensions", EMBEDDING_DIMENSIONS) != EMBEDDING_DIMENSIONS:
        raise SystemExit(
            f"Collection was built with {stored.get('embedding_model')}/{stored.get('embedding_dimensions')}, "
            f"config is {EMBEDDING_MODEL}/{EMBEDDING_DIMENSIONS}. Delete collection{COLLECTION_NAME} to rebuild."
        )
    return store


def add_with_retry(store: Chroma, batch: list[dict]):
    for attempt in range(MAX_RETRIES):
        try:
            store.add_texts(
                texts=[c["text"] for c in batch],
                metadatas=[to_metadata(c) for c in batch],
                ids=[c["chunk_id"] for c in batch],
            )
            return
        except Exception as e:  # rate limit, 네트워크 오류 등
            if attempt == MAX_RETRIES - 1:
                raise
            wait = 2 ** attempt * 5
            print(f"  재시도 {attempt + 1}/{MAX_RETRIES} ({type(e).__name__}), {wait}초 대기", file=sys.stderr)
            time.sleep(wait)


def main():
    with CHUNKS_PATH.open(encoding="utf-8") as f:
        chunks = [json.loads(line) for line in f]
    store = open_store()

    existing = store.get(include=["metadatas"])
    stored_hash = {i: (m or {}).get("text_hash") for i, m in zip(existing["ids"], existing["metadatas"])}
    wanted = {c["chunk_id"]: c for c in chunks}

    removed = [i for i in stored_hash if i not in wanted]
    pending = [c for c in chunks if stored_hash.get(c["chunk_id"]) != text_hash(c["text"])]
    print(f"청크 {len(chunks)}개 / 저장됨 {len(stored_hash)}개 → 임베딩 {len(pending)}개, 삭제 {len(removed)}개")

    if removed:
        store.delete(ids=removed)
    changed = [c["chunk_id"] for c in pending if c["chunk_id"] in stored_hash]
    if changed:
        store.delete(ids=changed)  # 내용이 바뀐 청크는 지우고 다시 넣는다

    for start in range(0, len(pending), ADD_BATCH_SIZE):
        add_with_retry(store, pending[start:start + ADD_BATCH_SIZE])
        print(f"  {min(start + ADD_BATCH_SIZE, len(pending))}/{len(pending)}")

    print(f"완료: 컬렉션 {COLLECTION_NAME} = {store._collection.count()}개")

    print("\n확인용 검색 (상위 3개, 코사인 거리)")
    for query in SMOKE_QUERIES:
        print(f"Q: {query}")
        for doc, score in store.similarity_search_with_score(query, k=3):
            m = doc.metadata
            label = m.get("new") if m.get("source") == "import_map" else f"{m.get('title')} > {m.get('section', '')}"
            print(f"  {score:.3f} [{m.get('source')}] {label}")


if __name__ == "__main__":
    main()
