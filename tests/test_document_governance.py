import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from rerank_rag.documents import load_documents


class DocumentGovernanceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.root = Path(self.directory.name)
        (self.root / "report.pdf").write_bytes(b"not a real PDF")

    def write_catalog(self, **changes):
        record = {
            "document_id": "report-001",
            "owner": "法务部",
            "classification": "internal",
            "approved": True,
        }
        record.update(changes)
        (self.root / "manifest.json").write_text(
            json.dumps({"documents": {"report.pdf": record}}, ensure_ascii=False),
            encoding="utf-8",
        )

    def test_missing_catalog_blocks_parsing(self):
        with patch("rerank_rag.documents.parse_document") as parse:
            with self.assertRaises(FileNotFoundError):
                load_documents(self.root)
        parse.assert_not_called()

    def test_unapproved_document_blocks_parsing(self):
        self.write_catalog(approved=False)
        with patch("rerank_rag.documents.parse_document") as parse:
            with self.assertRaises(PermissionError):
                load_documents(self.root)
        parse.assert_not_called()

    def test_top_secret_document_blocks_parsing(self):
        self.write_catalog(classification="top_secret")
        with patch("rerank_rag.documents.parse_document") as parse:
            with self.assertRaises(PermissionError):
                load_documents(self.root)
        parse.assert_not_called()

    def test_missing_file_registration_blocks_parsing(self):
        self.write_catalog()
        (self.root / "other.txt").write_text("content", encoding="utf-8")
        with patch("rerank_rag.documents.parse_document") as parse:
            with self.assertRaisesRegex(ValueError, "未登记"):
                load_documents(self.root)
        parse.assert_not_called()

    def test_approved_document_includes_registration(self):
        self.write_catalog()
        with patch("rerank_rag.documents.parse_document", return_value="Document text") as parse:
            documents = load_documents(self.root)
        parse.assert_called_once()
        self.assertEqual(documents, [{
            "source": "report.pdf",
            "text": "Document text",
            "document_id": "report-001",
            "owner": "法务部",
            "classification": "internal",
            "approved": True,
        }])


if __name__ == "__main__":
    unittest.main()
