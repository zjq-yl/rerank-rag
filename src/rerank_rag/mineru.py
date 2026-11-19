"""Use MinerU's hosted precision API to turn a local document into Markdown."""

from __future__ import annotations

import hashlib
import io
import os
import time
import zipfile
from pathlib import Path

import requests

from rerank_rag.config import PROJECT_ROOT, require_opt_in

API_ROOT = "https://mineru.net/api/v4"
POLL_INTERVAL_SECONDS = 3
POLL_TIMEOUT_SECONDS = 300
MODEL_VERSION = "vlm"


def _document_hash(path: Path) -> str:
    digest = hashlib.sha256()
    digest.update(MODEL_VERSION.encode("ascii"))
    with path.open("rb") as document:
        for block in iter(lambda: document.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _api_data(response: requests.Response) -> dict:
    response.raise_for_status()
    payload = response.json()
    if payload.get("code") != 0:
        raise RuntimeError(f"MinerU API 错误：{payload.get('msg', '未知错误')}")
    return payload["data"]


def parse_document(path: Path) -> str:
    """Parse a PDF or presentation through MinerU and cache the Markdown result."""
    cache_path = PROJECT_ROOT / ".cache" / "mineru" / f"{_document_hash(path)}.md"
    if cache_path.is_file():
        return cache_path.read_text(encoding="utf-8")

    require_opt_in("RAG_ALLOW_MINERU_UPLOAD", "向 MinerU 上传文档")
    api_key = os.getenv("MINERU_API_KEY")
    if not api_key:
        raise RuntimeError("MinerU 解析需要在根目录 .env 中配置 MINERU_API_KEY")

    headers = {"Authorization": f"Bearer {api_key}"}
    task = _api_data(
        requests.post(
            f"{API_ROOT}/file-urls/batch",
            headers=headers,
            json={"files": [{"name": path.name}], "model_version": MODEL_VERSION},
            timeout=30,
        )
    )
    batch_id = task["batch_id"]
    upload_urls = task["file_urls"]
    if len(upload_urls) != 1:
        raise RuntimeError("MinerU 未返回唯一的文档上传地址")

    # The signed upload URL belongs to object storage: do not send the API token.
    with path.open("rb") as document:
        upload = requests.put(upload_urls[0], data=document, timeout=180)
    if upload.status_code not in (200, 201):
        raise RuntimeError(f"MinerU 文档上传失败：HTTP {upload.status_code}")

    deadline = time.monotonic() + POLL_TIMEOUT_SECONDS
    while time.monotonic() < deadline:
        result = _api_data(
            requests.get(
                f"{API_ROOT}/extract-results/batch/{batch_id}",
                headers=headers,
                timeout=30,
            )
        )
        items = result.get("extract_result") or []
        if items:
            item = items[0]
            state = item.get("state")
            if state == "failed":
                raise RuntimeError(
                    f"MinerU 解析 {path.name} 失败：{item.get('err_msg', '未知错误')}"
                )
            if state == "done":
                zip_url = item.get("full_zip_url")
                if not zip_url:
                    raise RuntimeError("MinerU 任务完成，但没有返回结果 ZIP 地址")
                archive_response = requests.get(zip_url, timeout=180)
                archive_response.raise_for_status()
                with zipfile.ZipFile(io.BytesIO(archive_response.content)) as archive:
                    markdown_files = [
                        name
                        for name in archive.namelist()
                        if Path(name).name == "full.md"
                    ]
                    if not markdown_files:
                        raise RuntimeError("MinerU 结果 ZIP 中没有 full.md")
                    text = archive.read(markdown_files[0]).decode("utf-8")
                if not text.strip():
                    raise RuntimeError(f"MinerU 没有从 {path.name} 提取到文本")
                cache_path.parent.mkdir(parents=True, exist_ok=True)
                cache_path.write_text(text, encoding="utf-8")
                return text
        time.sleep(POLL_INTERVAL_SECONDS)

    raise TimeoutError(f"MinerU 解析 {path.name} 超时（batch_id={batch_id}）")
