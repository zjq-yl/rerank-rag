import chromadb
from rerank_rag.embedding import embed_chunks
from rerank_rag.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
)


def retrieve(
    question: str,
    top_k: int = 3,
) -> list[dict]:
    """把 Query 向量化，并从 Chroma 检索 Top-K。"""
    if not question.strip():
        raise ValueError("查询问题不能为空")

    if top_k <= 0:
        raise ValueError("top_k 必须大于 0")

    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    collection = client.get_collection(COLLECTION_NAME)
    count = collection.count()
    if count == 0:
        raise RuntimeError("向量库为空，请先建立索引")

    query_id = "__query__"
    query_result = embed_chunks(
        [
            {
                "id": query_id,
                "source": "query",
                "chunk_index": 0,
                "text": question,
            }
        ],
        is_query=True,
    )
    result = collection.query(
        query_embeddings=[query_result[query_id]],
        n_results=min(top_k, count),
        include=["documents", "metadatas", "distances"],
    )
    ids = (result.get("ids") or [[]])[0]
    documents = (result.get("documents") or [[]])[0]
    metadatas = (result.get("metadatas") or [[]])[0]
    distances = (result.get("distances") or [[]])[0]

    hits = []

    for chunk_id, text, metadata, distance in zip(
        ids,
        documents,
        metadatas,
        distances,
    ):
        if not text:
            continue

        metadata = metadata or {}
        hits.append(
            {
                "id": chunk_id,
                "source": metadata.get("source", "unknown"),
                "chunk_index": metadata.get("chunk_index", -1),
                "text": text,
                "score": 1.0 - float(distance),
            }
        )
    return hits
