"""Validate the local document catalog before any document is parsed."""

import json
from pathlib import Path


CLASSIFICATIONS = {"public", "internal", "confidential", "top_secret"}
CHUNK_METADATA_FIELDS = (
    "source", "chunk_index", "document_id", "owner", "classification", "approved"
)


def validated_chunk_metadata(chunk: dict) -> dict:
    """Return Chroma-compatible metadata, rejecting incomplete or forbidden chunks."""
    missing = [field for field in CHUNK_METADATA_FIELDS if field not in chunk]
    if missing:
        raise ValueError(f"Chunk {chunk.get('id', '<unknown>')} 缺少元数据：{', '.join(missing)}")

    metadata = {field: chunk[field] for field in CHUNK_METADATA_FIELDS}
    for field in ("source", "document_id", "owner"):
        if not isinstance(metadata[field], str) or not metadata[field].strip():
            raise ValueError(f"Chunk {chunk.get('id', '<unknown>')} 的 {field} 无效")
    if type(metadata["chunk_index"]) is not int or metadata["chunk_index"] < 0:
        raise ValueError(f"Chunk {chunk.get('id', '<unknown>')} 的 chunk_index 无效")
    if not isinstance(metadata["classification"], str) or metadata["classification"] not in CLASSIFICATIONS:
        raise ValueError(f"Chunk {chunk.get('id', '<unknown>')} 的 classification 无效")
    if metadata["classification"] == "top_secret" or metadata["approved"] is not True:
        raise PermissionError(f"Chunk {chunk.get('id', '<unknown>')} 未获准入库")
    return metadata
CHUNK_METADATA_FIELDS = (
    "source", "chunk_index", "document_id", "owner", "classification", "approved"
)


def validated_chunk_metadata(chunk: dict) -> dict:
    """Return Chroma-compatible metadata, rejecting incomplete or forbidden chunks."""
    missing = [field for field in CHUNK_METADATA_FIELDS if field not in chunk]
    if missing:
        raise ValueError(f"Chunk {chunk.get('id', '<unknown>')} 缺少元数据：{', '.join(missing)}")

    metadata = {field: chunk[field] for field in CHUNK_METADATA_FIELDS}
    for field in ("source", "document_id", "owner"):
        if not isinstance(metadata[field], str) or not metadata[field].strip():
            raise ValueError(f"Chunk {chunk.get('id', '<unknown>')} 的 {field} 无效")
    if type(metadata["chunk_index"]) is not int or metadata["chunk_index"] < 0:
        raise ValueError(f"Chunk {chunk.get('id', '<unknown>')} 的 chunk_index 无效")
    if metadata["classification"] not in CLASSIFICATIONS:
        raise ValueError(f"Chunk {chunk.get('id', '<unknown>')} 的 classification 无效")
    if metadata["classification"] == "top_secret" or metadata["approved"] is not True:
        raise PermissionError(f"Chunk {chunk.get('id', '<unknown>')} 未获准入库")
    return metadata


def load_catalog(root: Path, sources: list[str]) -> dict[str, dict]:
    catalog_path = root / "manifest.json"
    if not catalog_path.is_file():
        raise FileNotFoundError(
            f"缺少文档登记文件：{catalog_path}。请参考 data-manifest.example.json。"
        )

    try:
        catalog = json.loads(catalog_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"无法读取文档登记文件：{catalog_path}") from exc

    if not isinstance(catalog, dict) or set(catalog) != {"documents"}:
        raise ValueError("manifest.json 顶层必须只有 documents 对象")
    records = catalog["documents"]
    if not isinstance(records, dict):
        raise ValueError("manifest.json 的 documents 必须是对象")

    missing = set(sources) - set(records)
    extra = set(records) - set(sources)
    if missing or extra:
        raise ValueError(
            "文档登记与 data/ 文件不一致："
            f"未登记 {sorted(missing)}；无对应文件 {sorted(extra)}"
        )

    document_ids = set()
    for source in sources:
        record = records[source]
        if not isinstance(record, dict) or set(record) != {
            "document_id", "owner", "classification", "approved"
        }:
            raise ValueError(f"{source} 的登记字段必须为 document_id、owner、classification、approved")
        for field in ("document_id", "owner"):
            if not isinstance(record[field], str) or not record[field].strip():
                raise ValueError(f"{source} 的 {field} 必须是非空字符串")
        if record["document_id"] in document_ids:
            raise ValueError(f"重复的 document_id：{record['document_id']}")
        document_ids.add(record["document_id"])
        if not isinstance(record["classification"], str) or record["classification"] not in CLASSIFICATIONS:
            raise ValueError(f"{source} 的 classification 无效：{record['classification']}")
        if type(record["approved"]) is not bool:
            raise ValueError(f"{source} 的 approved 必须是布尔值")
        if record["classification"] == "top_secret" or not record["approved"]:
            raise PermissionError(f"文档未获准入库：{source}")

    return records
