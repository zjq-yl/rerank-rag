"""Local cross-encoder reranking for retrieved document chunks."""

from __future__ import annotations

from rerank_rag.config import (
    RERANK_BATCH_SIZE,
    RERANK_MODEL_PATH,
    RERANK_TOP_N,
)
from sentence_transformers import CrossEncoder
import torch

_reranker: CrossEncoder | None = None


def get_reranker() -> CrossEncoder:
    """Load the local BGE reranker once and reuse it."""
    global _reranker

    if _reranker is None:
        if not RERANK_MODEL_PATH.is_dir():
            raise FileNotFoundError(f"本地 Rerank 模型不存在：{RERANK_MODEL_PATH}")

        _reranker = CrossEncoder(
            str(RERANK_MODEL_PATH),
            device="cuda" if torch.cuda.is_available() else "cpu",
            local_files_only=True,
        )

    return _reranker


def rerank_hits(
    question: str,
    candidates: list[dict],
    top_n: int = RERANK_TOP_N,
) -> list[dict]:
    """Score query/chunk pairs and return the best Top-N chunks."""
    if not question.strip():
        raise ValueError("查询问题不能为空")

    if top_n <= 0:
        raise ValueError("top_n 必须大于 0")

    if not candidates:
        return []

    pairs = [(question, candidate["text"]) for candidate in candidates]

    scores = get_reranker().predict(
        pairs,
        batch_size=RERANK_BATCH_SIZE,
        show_progress_bar=False,
        convert_to_numpy=True,
    )

    if len(scores) != len(candidates):
        raise RuntimeError("Rerank 返回数量与候选 Chunk 数量不一致")

    ranked = []

    for candidate, score in zip(candidates, scores):
        hit = dict(candidate)
        hit["rerank_score"] = float(score)
        ranked.append(hit)

    ranked.sort(
        key=lambda hit: hit["rerank_score"],
        reverse=True,
    )

    return ranked[: min(top_n, len(ranked))]
