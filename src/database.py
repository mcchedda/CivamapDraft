"""Qdrant semantic index with locally generated FastEmbed vectors."""

import hashlib
import json
import os
from pathlib import Path

from fastembed import TextEmbedding
from qdrant_client import QdrantClient, models

from src.retrieval import search_resources

COLLECTION = "civamap_resources_v1"
EMBEDDING_MODEL = "BAAI/bge-small-en-v1.5"
VECTOR_SIZE = 384
ROOT = Path(__file__).resolve().parents[1]


def get_client() -> QdrantClient:
    url = os.getenv("QDRANT_URL", "").strip()
    if url:
        return QdrantClient(url=url, api_key=os.getenv("QDRANT_API_KEY") or None, timeout=60)
    local_path = ROOT / ".qdrant"
    local_path.mkdir(parents=True, exist_ok=True)
    return QdrantClient(path=str(local_path))


def get_embedder() -> TextEmbedding:
    # First use downloads the embedding model; subsequent uses are local.
    return TextEmbedding(model_name=EMBEDDING_MODEL)


def as_document(row: dict) -> str:
    keys = (
        "Resource Name", "Category", "Services Provided", "Eligibility and Cost",
        "CHW Insider Tips", "Primary Service Area", "Search Text (for semantic search)",
    )
    return "\n".join(f"{key}: {row.get(key, '')}" for key in keys if str(row.get(key, "")).strip())


def digest_resources(resources: list[dict]) -> str:
    raw = json.dumps(resources, sort_keys=True, default=str, ensure_ascii=False).encode()
    return hashlib.sha256(raw).hexdigest()


def ensure_index(client: QdrantClient, embedder: TextEmbedding, resources: list[dict], force: bool = False) -> bool:
    """Build if missing/stale. Return True if reindexed. Safe for a single-user prototype."""
    if not resources:
        raise ValueError("Resource directory is empty")
    digest = digest_resources(resources)
    stamp = ROOT / ".qdrant_index_stamp"
    remote = bool(os.getenv("QDRANT_URL", "").strip())
    # For remote stores, force explicit rebuild when the source changes or is unknown.
    matches = stamp.exists() and stamp.read_text().strip() == digest
    exists = client.collection_exists(COLLECTION)
    has_count = exists and client.count(COLLECTION, exact=True).count == len(resources)
    if not force and exists and has_count and matches:
        return False
    if exists:
        client.delete_collection(COLLECTION)
    client.create_collection(
        collection_name=COLLECTION,
        vectors_config=models.VectorParams(size=VECTOR_SIZE, distance=models.Distance.COSINE),
    )
    texts = [as_document(row) for row in resources]
    vectors = embedder.embed(texts)
    batch = []
    for i, (row, vector) in enumerate(zip(resources, vectors), start=1):
        batch.append(models.PointStruct(id=i, vector=vector.tolist(), payload=dict(row)))
        if len(batch) >= 32:
            client.upsert(collection_name=COLLECTION, points=batch, wait=True)
            batch.clear()
    if batch:
        client.upsert(collection_name=COLLECTION, points=batch, wait=True)
    stamp.write_text(digest)
    return True


def search_qdrant(client: QdrantClient, embedder: TextEmbedding, resources: list[dict], query: str, limit: int = 5) -> list[dict]:
    """Fuse dense semantic matches with a simple keyword rank (local hybrid prototype)."""
    if not query.strip():
        return []
    vector = next(iter(embedder.query_embed(query))).tolist()
    dense = client.query_points(
        collection_name=COLLECTION, query=vector, limit=min(max(limit * 3, 12), 40), with_payload=True,
    ).points
    keyword = search_resources(resources, query, limit=min(max(limit * 3, 12), 40))
    fused = {}
    for rank, point in enumerate(dense, 1):
        row = dict(point.payload or {})
        name = str(row.get("Resource Name", ""))
        if not name:
            continue
        fused.setdefault(name, {"score": 0.0, "row": row})["score"] += 1.0 / (60 + rank)
    for rank, row in enumerate(keyword, 1):
        name = str(row.get("Resource Name", ""))
        fused.setdefault(name, {"score": 0.0, "row": row})["score"] += 1.0 / (60 + rank)
    return [v["row"] for v in sorted(fused.values(), key=lambda v: -v["score"])[:limit]]
