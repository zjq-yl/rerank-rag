"""External document and context transfers require explicit opt-in."""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rerank_rag import generation, mineru
from rerank_rag.config import require_opt_in


class ExternalTransferTests(unittest.TestCase):
    def test_mineru_upload_is_blocked_before_network_call(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "private.pdf"
            path.write_bytes(b"private document")
            with (
                patch.object(mineru, "PROJECT_ROOT", Path(directory)),
                patch.dict(os.environ, {"RAG_ALLOW_MINERU_UPLOAD": "false"}),
                patch.object(mineru.requests, "post") as post,
            ):
                with self.assertRaisesRegex(RuntimeError, "RAG_ALLOW_MINERU_UPLOAD"):
                    mineru.parse_document(path)
                post.assert_not_called()

    def test_llm_context_transfer_is_blocked_before_client_creation(self):
        hits = [{"id": "chunk-1", "source": "private.txt", "text": "private"}]
        with (
            patch.dict(os.environ, {"RAG_ALLOW_LLM_CONTEXT_TRANSFER": "false"}),
            patch.object(generation, "OpenAI") as client,
        ):
            with self.assertRaisesRegex(RuntimeError, "RAG_ALLOW_LLM_CONTEXT_TRANSFER"):
                generation.generate_answer("question", hits)
            client.assert_not_called()

    def test_explicit_true_enables_operation(self):
        with patch.dict(os.environ, {"RAG_ALLOW_MINERU_UPLOAD": "true"}):
            require_opt_in("RAG_ALLOW_MINERU_UPLOAD", "test")


if __name__ == "__main__":
    unittest.main()
