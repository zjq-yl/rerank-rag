import argparse

import chromadb

from rerank_rag.config import (
    CHROMA_DIR,
    COLLECTION_NAME,
    EMBED_BATCH_SIZE,
    RERANK_CANDIDATE_K,
    RERANK_TOP_N,
)
from rerank_rag.documents import (
    create_chunks,
    load_documents,
)
from rerank_rag.embedding import embed_chunks
from rerank_rag.generation import generate_answer
from rerank_rag.governance import validated_chunk_metadata
from rerank_rag.rerank import rerank_hits
from rerank_rag.vector_store import retrieve


def build_index(reset: bool = True) -> int:
    """离线建库：Chunks → 本地 BGE 向量 → Chroma。"""
    documents = load_documents()
    chunks = create_chunks(documents)
    chunk_metadatas = [validated_chunk_metadata(chunk) for chunk in chunks]
    chunk_vectors = embed_chunks(chunks)
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    existing_names = {collection.name for collection in client.list_collections()}

    if reset and COLLECTION_NAME in existing_names:
        client.delete_collection(COLLECTION_NAME)

    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    for start in range(0, len(chunks), EMBED_BATCH_SIZE):
        batch = chunks[start : start + EMBED_BATCH_SIZE]

        collection.upsert(
            ids=[chunk["id"] for chunk in batch],
            documents=[chunk["text"] for chunk in batch],
            embeddings=[chunk_vectors[chunk["id"]] for chunk in batch],
            metadatas=chunk_metadatas[start : start + EMBED_BATCH_SIZE],
        )

    return collection.count()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="本地文档 RAG 问答",
    )
    subparsers = parser.add_subparsers(
        dest="command",
        required=True,
    )

    index_parser = subparsers.add_parser(
        "index",
        help="建立本地 Chroma 索引",
    )
    index_parser.add_argument(
        "--keep-existing",
        action="store_true",
        help="保留已有集合中的 Chunk",
    )

    web_parser = subparsers.add_parser("web", help="启动本地网页界面")
    web_parser.add_argument("--host", default="127.0.0.1", help="监听地址，默认 127.0.0.1")
    web_parser.add_argument("--port", type=int, default=8765, help="监听端口，默认 8765")

    ask_parser = subparsers.add_parser("ask", help="使用向量检索结果回答问题")
    rerank_parser = subparsers.add_parser(
        "ask-rerank", help="向量召回后重排，再回答问题"
    )
    for query_parser in (ask_parser, rerank_parser):
        query_parser.add_argument("question", help="要查询的问题")
        query_parser.add_argument(
            "--retrieval-only",
            action="store_true",
            help="只显示检索结果，不调用生成模型",
        )
    ask_parser.add_argument(
        "--top-k",
        type=int,
        default=RERANK_TOP_N,
        help=f"直接用于回答的向量检索结果数，默认 {RERANK_TOP_N}",
    )
    rerank_parser.add_argument(
        "--candidate-k",
        type=int,
        default=RERANK_CANDIDATE_K,
        help=f"向量召回候选数，默认 {RERANK_CANDIDATE_K}",
    )
    rerank_parser.add_argument(
        "--rerank-top-n",
        type=int,
        default=RERANK_TOP_N,
        help=f"重排后保留结果数，默认 {RERANK_TOP_N}",
    )

    args = parser.parse_args()

    if args.command == "index":
        count = build_index(
            reset=not args.keep_existing,
        )
        print(f"索引完成：{count} 个 Chunk")
        print(f"Chroma 目录：{CHROMA_DIR}")
        return

    if args.command == "web":
        from rerank_rag.web import serve

        serve(args.host, args.port)
        return

    if args.command == "ask":
        hits = retrieve(args.question, top_k=args.top_k)
        print(f"\n向量检索返回 {len(hits)} 个结果")
    else:
        candidates = retrieve(args.question, top_k=args.candidate_k)
        hits = rerank_hits(args.question, candidates, top_n=args.rerank_top_n)
        print(
            f"\n向量召回 {len(candidates)} 个候选，重排后保留 {len(hits)} 个结果"
        )

    for number, hit in enumerate(hits, start=1):
        score_text = f"vector_score={hit['score']:.4f}"
        if "rerank_score" in hit:
            score_text += f" rerank_score={hit['rerank_score']:.4f}"
        print(f"[{number}] {hit['id']} source={hit['source']} {score_text}")
        print(f"    {hit['text'].replace(chr(10), ' ')[:160]}")

    if args.retrieval_only:
        return

    print("\n回答：")
    answer = generate_answer(args.question, hits)
    print(answer)


if __name__ == "__main__":
    main()
