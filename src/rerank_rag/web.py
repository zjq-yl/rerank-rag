"""Local web interface for document retrieval and question answering."""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

from rerank_rag.config import RERANK_CANDIDATE_K, RERANK_TOP_N
from rerank_rag.generation import generate_answer
from rerank_rag.rerank import rerank_hits
from rerank_rag.vector_store import retrieve

STATIC_DIR = Path(__file__).resolve().parent / "static"
STATIC_FILES = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
}


def answer_question(question: str, use_rerank: bool, retrieval_only: bool) -> dict:
    """Run one RAG query and return the answer with its source chunks."""
    question = question.strip()
    if not question or len(question) > 1000:
        raise ValueError("问题长度需为 1 到 1000 个字符")

    if use_rerank:
        candidates = retrieve(question, top_k=RERANK_CANDIDATE_K)
        hits = rerank_hits(question, candidates, top_n=RERANK_TOP_N)
    else:
        hits = retrieve(question, top_k=RERANK_TOP_N)

    return {
        "answer": None if retrieval_only else generate_answer(question, hits),
        "hits": hits,
    }


class RAGHandler(BaseHTTPRequestHandler):
    def _send(self, status: int, body: bytes, content_type: str) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, status: int, data: dict) -> None:
        self._send(status, json.dumps(data, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_GET(self) -> None:
        static_file = STATIC_FILES.get(self.path)
        if static_file is None:
            self.send_error(404)
            return
        filename, content_type = static_file
        self._send(200, (STATIC_DIR / filename).read_bytes(), content_type)

    def do_POST(self) -> None:
        if self.path != "/api/ask":
            self.send_error(404)
            return
        try:
            size = int(self.headers.get("Content-Length", "0"))
            if not 0 < size <= 16_384:
                raise ValueError("请求内容不能为空且不能超过 16 KB")
            data = json.loads(self.rfile.read(size))
            if not isinstance(data, dict) or not isinstance(data.get("question"), str):
                raise ValueError("请提供文本问题")
            if type(data.get("use_rerank")) is not bool or type(data.get("retrieval_only")) is not bool:
                raise ValueError("检索选项格式不正确")
            result = answer_question(data["question"], data["use_rerank"], data["retrieval_only"])
        except (ValueError, json.JSONDecodeError) as exc:
            self._json(400, {"error": str(exc)})
            return
        except Exception as exc:
            self._json(500, {"error": str(exc)})
            return
        self._json(200, result)


def serve(host: str = "127.0.0.1", port: int = 8765) -> None:
    """Serve the interface on the local machine until interrupted."""
    server = HTTPServer((host, port), RAGHandler)
    print(f"RAG 网页已启动：http://{host}:{port}")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
