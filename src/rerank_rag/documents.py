from pathlib import Path

from rerank_rag.config import (
    CHUNK_OVERLAP,
    CHUNK_SIZE,
    DATA_DIR,
)
from rerank_rag.mineru import parse_pdf


def _read_docx(path: Path) -> str:
    """Read paragraphs and tables in their document order."""
    from docx import Document
    from docx.table import Table

    parts: list[str] = []
    for block in Document(path).iter_inner_content():
        if isinstance(block, Table):
            for row in block.rows:
                cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
                if any(cells):
                    parts.append(" | ".join(cells))
        elif block.text.strip():
            parts.append(block.text.strip())
    return "\n".join(parts)


def load_documents(data_dir:Path=DATA_DIR) -> list[dict]:
    """读取 data 目录下的 txt、md、docx 和 pdf 文件。"""
    root=Path(data_dir).resolve()
    suffixes={".txt", ".md", ".docx", ".pdf"}

    files=sorted(
        path
        for path in root.rglob("*")
        if path.is_file() and path.suffix.lower() in suffixes
    )
    if not files:
        raise FileNotFoundError(f"没有在 {root} 中找到 txt、md、docx 或 pdf 文件")

    documents=[]
    for path in files:
        if path.suffix.lower() == ".docx":
            text = _read_docx(path)
        elif path.suffix.lower() == ".pdf":
            text = parse_pdf(path)
        else:
            text = path.read_text(encoding="utf-8")

        if not text.strip():
            continue
        documents.append(
            {
                "source":path.relative_to(root).as_posix(),
                "text":text,
            }
        )
    if not documents:
        raise RuntimeError("找到了文档，但是文档内容为空")
    return documents

def split_text(
        text:str,
        chunk_size:int=CHUNK_SIZE,
        overlap:int=CHUNK_OVERLAP,
)-> list[str]:
    """把长文本切成带有重叠的固定长度文本块。"""
    if chunk_size<=0:
        raise ValueError("chunk_size必须大于0")
    if overlap < 0 or overlap >= chunk_size:
        raise ValueError("overlap必须满足0 <= overlap < chunk_size")

    cleaned="\n".join(
        line.strip()
        for line in text.splitlines()
        if line.strip()
    )
    chunks=[]
    start=0

    while start < len(cleaned):
        end=min(start+chunk_size,len(cleaned))
        chunk = cleaned[start:end].strip()

        if chunk:
            chunks.append(chunk)
        if end==len(cleaned):
            break
        start=end-overlap
    return chunks

def create_chunks(documents:list[dict])->list[dict]:
    """为每个文本块增加来源、块编号和唯一 ID。"""
    chunks=[]
    for document in documents:
        text_chunks=split_text(document["text"])
        for chunk_index,text in enumerate(text_chunks):
            chunks.append(
                {
                    "id": f"{document['source']}-{chunk_index}",
                    "source": document["source"],
                    "chunk_index": chunk_index,
                    "text": text,
                }
            )
    return chunks
