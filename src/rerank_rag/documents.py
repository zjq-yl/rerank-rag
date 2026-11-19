from pathlib import Path

from rerank_rag.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_DIR,
)
from rerank_rag.governance import load_catalog
from rerank_rag.mineru import parse_document


DOCLING_SUFFIXES = {
    ".docx", ".xlsx", ".ppt", ".pptx", ".html", ".htm", ".csv",
    ".epub", ".odt", ".ods", ".odp",
}
PRESENTATION_SUFFIXES = {".ppt", ".pptx"}


def load_documents(data_dir: Path = DATA_DIR) -> list[dict]:
    """读取 data 目录中的文本、PDF 和 Docling 支持的文档。"""
    root = Path(data_dir).resolve()
    suffixes = {".txt", ".md", ".pdf"} | DOCLING_SUFFIXES

    files = sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    )
    if not files:
        raise FileNotFoundError(f"在 {root} 中没有找到支持的文档")
    if any(not path.resolve().is_relative_to(root) for path in files):
        raise ValueError("data/ 中的文档不能指向目录外的文件")

    sources = [path.relative_to(root).as_posix() for path in files]
    catalog = load_catalog(root, sources)

    documents = []
    converter = None
    for path in files:
        source = path.relative_to(root).as_posix()
        if path.suffix.lower() == ".pdf":
            text = parse_document(path)
        elif path.suffix.lower() in DOCLING_SUFFIXES:
            try:
                if converter is None:
                    from docling.document_converter import DocumentConverter

                    converter = DocumentConverter()
                text = converter.convert(path).document.export_to_markdown()
                if path.suffix.lower() in PRESENTATION_SUFFIXES and not text.strip():
                    raise ValueError("Docling 未提取到文字")
            except Exception as exc:
                if path.suffix.lower() not in PRESENTATION_SUFFIXES:
                    raise
                try:
                    text = parse_document(path)
                except Exception as fallback_exc:
                    raise RuntimeError(
                        f"{path.name} 的 Docling 和 MinerU 解析均失败；"
                        f"Docling: {exc}；MinerU: {fallback_exc}"
                    ) from fallback_exc
        else:
            text = path.read_text(encoding="utf-8")

        if not text.strip():
            continue
        documents.append(
            {
                "source": source,
                "text": text,
                **catalog[source],
            }
        )
    if not documents:
        raise RuntimeError("找到了文档，但是文档内容为空")
    return documents


def split_text(
    text: str,
    chunk_size: int = CHUNK_SIZE,
    overlap: int = CHUNK_OVERLAP,
) -> list[str]:
    """把长文本切成带有重叠的固定长度文本块。"""
    if chunk_size <= 0:
        raise ValueError("chunk_size必须大于0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap必须满足0 <= overlap < chunk_size")

    cleaned = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    chunks = []
    start = 0

    while start < len(cleaned):
        end = min(start + chunk_size, len(cleaned))
        chunk = cleaned[start:end].strip()

        if chunk:
            chunks.append(chunk)
        if end == len(cleaned):
            break
        start = end - overlap
    return chunks


def create_chunks(documents: list[dict]) -> list[dict]:
    """为每个文本块增加来源、块编号和唯一 ID。"""
    chunks = []
    for document in documents:
        text_chunks = split_text(document["text"])
        for chunk_index, text in enumerate(text_chunks):
            chunks.append(
                {
                    "id": f"{document['source']}-{chunk_index}",
                    "source": document["source"],
                    "chunk_index": chunk_index,
                    "text": text,
                    "document_id": document.get("document_id"),
                    "owner": document.get("owner"),
                    "classification": document.get("classification"),
                    "approved": document.get("approved"),
                }
            )
    return chunks
