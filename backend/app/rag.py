"""ChromaDB vector store with a lightweight local char n-gram embedding."""

from typing import Any, Optional

from chromadb import PersistentClient
from chromadb.config import Settings
from sklearn.feature_extraction.text import HashingVectorizer, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from .config import CHROMA_DIR, EMBEDDING_DIM, RERANK_BACKEND

COLLECTION_NAME = "ecommerce_ticket_rag"

_vectorizer = HashingVectorizer(
    analyzer="char_wb",
    ngram_range=(2, 4),
    n_features=EMBEDDING_DIM,
    norm="l2",
)
_client: Optional[PersistentClient] = None
_client_path: Optional[str] = None
_keyword_vectorizer = TfidfVectorizer(
    analyzer="char_wb",
    ngram_range=(1, 3),
    max_features=5000,
)
_keyword_vectors = None
_keyword_metadatas: list[dict[str, Any]] = []


def _get_collection():
    global _client, _client_path
    path = str(CHROMA_DIR)
    if _client is None or _client_path != path:
        _client = PersistentClient(path=path, settings=Settings(anonymized_telemetry=False))
        _client_path = path
    return _client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )


def _embed(texts: list[str]) -> list[list[float]]:
    matrix = _vectorizer.transform(texts).toarray()
    return matrix.astype(float).tolist()


def index_documents(tickets: list[dict], knowledge: list[dict]) -> int:
    global _keyword_vectors, _keyword_metadatas
    collection = _get_collection()
    existing_ids = collection.get(include=[])["ids"]
    if existing_ids:
        collection.delete(ids=existing_ids)

    ids: list[str] = []
    documents: list[str] = []
    metadatas: list[dict[str, Any]] = []

    for row in tickets:
        ids.append(f"ticket-{row['id']}")
        documents.append(f"【工单】{row['title']} {row['description']} {row['resolution']}")
        metadatas.append(
            {
                "id": row["id"],
                "category": row["category"],
                "title": row["title"],
                "description": row["description"],
                "resolution": row["resolution"],
                "status": row["status"],
                "priority": row["priority"],
                "created_at": row["created_at"],
                "source": "工单",
            }
        )

    for doc in knowledge:
        ids.append(f"kb-{doc['id']}")
        documents.append(f"【知识库】{doc['title']} {doc['content']}")
        metadatas.append(
            {
                "id": doc["id"],
                "category": doc["category"],
                "title": doc["title"],
                "description": doc["content"],
                "resolution": doc["content"],
                "status": "已解决",
                "priority": "",
                "created_at": doc["created_at"],
                "source": "知识库",
            }
        )

    if ids:
        collection.upsert(
            ids=ids,
            documents=documents,
            embeddings=_embed(documents),
            metadatas=metadatas,
        )
        _keyword_vectors = _keyword_vectorizer.fit_transform(documents)
        _keyword_metadatas = metadatas
    else:
        _keyword_vectors = None
        _keyword_metadatas = []
    return collection.count()


def _result_from_meta(meta: dict, content: str, score: float) -> dict:
    return {
        "id": str(meta.get("id") or ""),
        "category": str(meta.get("category") or ""),
        "title": str(meta.get("title") or ""),
        "description": str(meta.get("description") or ""),
        "resolution": str(meta.get("resolution") or ""),
        "content": str(content or ""),
        "score": round(float(score), 4),
        "source": str(meta.get("source") or "工单"),
    }


def _char_ngrams(text: str, n: int = 2) -> set[str]:
    normalized = "".join(ch for ch in text.lower() if not ch.isspace())
    return {normalized[i : i + n] for i in range(max(0, len(normalized) - n + 1))}


def _rerank_heuristic(query: str, results: list[dict]) -> list[dict]:
    query_grams = _char_ngrams(query)
    if not query_grams:
        return results
    for item in results:
        text = f"{item['title']} {item['description']} {item['resolution']}"
        doc_grams = _char_ngrams(text)
        overlap = len(query_grams & doc_grams) / max(1, len(query_grams | doc_grams))
        item["score"] = round(float(item.get("score", 0)) * 0.6 + overlap * 0.4, 4)
    return sorted(results, key=lambda item: item["score"], reverse=True)


def vector_search(
    query: str,
    category: str = "",
    top_k: int = 3,
    rerank: bool = False,
) -> list[dict]:
    collection = _get_collection()
    if collection.count() == 0:
        return []
    result = collection.query(
        query_embeddings=_embed([query]),
        n_results=max(1, int(top_k)),
        where={"category": category} if category else None,
        include=["documents", "metadatas", "distances"],
    )
    ids = result.get("ids", [[]])[0]
    if not ids:
        return []
    documents = result.get("documents", [[]])[0]
    metadatas = result.get("metadatas", [[]])[0]
    distances = result.get("distances", [[]])[0]
    vector_results: list[dict] = []
    for index, doc_id in enumerate(ids):
        meta = metadatas[index] if index < len(metadatas) else {}
        document = documents[index] if index < len(documents) else ""
        distance = float(distances[index]) if index < len(distances) else 1.0
        vector_results.append(
            _result_from_meta(meta, document, max(0.0, 1.0 - distance))
        )

    keyword_results: list[dict] = []
    if _keyword_vectors is not None:
        query_vector = _keyword_vectorizer.transform([query])
        scores = cosine_similarity(query_vector, _keyword_vectors)[0]
        ranked = sorted(
            (
                (meta, float(score))
                for meta, score in zip(_keyword_metadatas, scores)
                if not category or meta.get("category") == category
            ),
            key=lambda item: item[1],
            reverse=True,
        )[: max(int(top_k), 3)]
        for meta, score in ranked:
            content = f"{meta.get('title', '')} {meta.get('description', '')} {meta.get('resolution', '')}"
            keyword_results.append(_result_from_meta(meta, content, score))

    merged: dict[str, dict] = {}
    for ranked_items in (vector_results, keyword_results):
        for rank, item in enumerate(ranked_items, start=1):
            item_id = item["id"]
            entry = merged.setdefault(item_id, item)
            entry["_rrf"] = entry.get("_rrf", 0.0) + 1.0 / (60 + rank)

    output = sorted(
        merged.values(),
        key=lambda item: item.get("_rrf", 0.0),
        reverse=True,
    )[: int(top_k)]
    for item in output:
        item.pop("_rrf", None)
    if rerank:
        output = _rerank_heuristic(query, output)
    return output


def vector_db_stats() -> dict:
    collection = _get_collection()
    return {
        "backend": "chromadb",
        "path": str(CHROMA_DIR),
        "collection": collection.name,
        "document_count": collection.count(),
        "embedding_dim": EMBEDDING_DIM,
        "embedding_backend": "hashing-char-ngram-2-4-l2",
        "keyword_backend": "tfidf-char-ngram-1-3",
        "retrieval_backend": "hybrid-rrf-chroma-tfidf",
        "rerank_backend": RERANK_BACKEND,
    }
