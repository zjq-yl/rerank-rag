from rerank_rag.config import (
    BGE_QUERY_PREFIX,
    EMBED_BATCH_SIZE,
    EMBEDDING_MODEL_PATH,
)
from sentence_transformers import SentenceTransformer

_embedding_model: SentenceTransformer | None = None


def embed_chunks(
    chunks: list[dict],
    is_query: bool = False,
) -> dict[str, list[float]]:
    """使用本地 BGE 模型生成向量。"""
    global _embedding_model

    if not chunks:
        return {}

    if _embedding_model is None:
        if not EMBEDDING_MODEL_PATH.is_dir():
            raise FileNotFoundError(
                f"本地 Embedding 模型不存在：{EMBEDDING_MODEL_PATH}"
            )

        _embedding_model = SentenceTransformer(
            str(EMBEDDING_MODEL_PATH),
            device="cpu",
            local_files_only=True,
        )

    texts = [chunk["text"] for chunk in chunks]

    if is_query:
        texts = [BGE_QUERY_PREFIX + text for text in texts]

    embeddings = _embedding_model.encode(
        texts,
        batch_size=EMBED_BATCH_SIZE,
        normalize_embeddings=True,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    return {
        chunk["id"]: embedding.tolist() for chunk, embedding in zip(chunks, embeddings)
    }
