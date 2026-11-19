import unittest
from unittest.mock import patch

from rerank_rag.cli import build_index
from rerank_rag.documents import create_chunks


class ChunkMetadataTests(unittest.TestCase):
    def setUp(self):
        self.document = {
            "source": "policies/leave.md",
            "text": "Annual leave policy",
            "document_id": "leave-001",
            "owner": "HR",
            "classification": "internal",
            "approved": True,
        }

    def test_catalog_fields_are_written_to_chroma(self):
        with (
            patch("rerank_rag.cli.load_documents", return_value=[self.document]),
            patch("rerank_rag.cli.embed_chunks", return_value={"policies/leave.md-0": [0.1, 0.2]}),
            patch("rerank_rag.cli.chromadb.PersistentClient") as client_factory,
        ):
            client = client_factory.return_value
            client.list_collections.return_value = []
            collection = client.get_or_create_collection.return_value
            collection.count.return_value = 1
            self.assertEqual(build_index(), 1)

        self.assertEqual(collection.upsert.call_args.kwargs["metadatas"], [{
            "source": "policies/leave.md",
            "chunk_index": 0,
            "document_id": "leave-001",
            "owner": "HR",
            "classification": "internal",
            "approved": True,
        }])

    def test_missing_metadata_stops_before_embedding_or_database_change(self):
        document = {**self.document}
        del document["owner"]
        with (
            patch("rerank_rag.cli.load_documents", return_value=[document]),
            patch("rerank_rag.cli.embed_chunks") as embed,
            patch("rerank_rag.cli.chromadb.PersistentClient") as client_factory,
        ):
            with self.assertRaisesRegex(ValueError, "owner"):
                build_index()
        embed.assert_not_called()
        client_factory.assert_not_called()

    def test_forbidden_document_stops_before_embedding(self):
        document = {**self.document, "classification": "top_secret"}
        with (
            patch("rerank_rag.cli.load_documents", return_value=[document]),
            patch("rerank_rag.cli.embed_chunks") as embed,
        ):
            with self.assertRaises(PermissionError):
                build_index()
        embed.assert_not_called()

    def test_each_chunk_keeps_document_metadata(self):
        chunks = create_chunks([self.document])
        self.assertEqual(chunks[0]["document_id"], "leave-001")
        self.assertEqual(chunks[0]["classification"], "internal")


if __name__ == "__main__":
    unittest.main()
