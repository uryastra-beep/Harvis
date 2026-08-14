from __future__ import annotations

from datetime import datetime, timezone

from harvis.features.semantic_search import SemanticFileSearch


def test_semantic_file_search_uses_document_content_and_aliases(tmp_path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    target = documents / "notes.txt"
    target.write_text(
        "Ancient Greece developed influential philosophy and architecture.",
        encoding="utf-8",
    )
    (documents / "shopping.txt").write_text("milk bread", encoding="utf-8")
    search = SemanticFileSearch(tmp_path / "index.json")

    result = search.search(
        "encuentra el documento sobre Grecia",
        roots=[documents],
        now=datetime.now(timezone.utc),
    )

    assert result["status"] == "completed"
    assert result["matches"][0]["path"] == str(target.resolve())
    assert "document content match" in result["matches"][0]["reason"]


def test_semantic_search_records_prior_use(tmp_path) -> None:
    documents = tmp_path / "Documents"
    documents.mkdir()
    target = documents / "Greece.pdf"
    target.write_bytes(b"not a real PDF")
    search = SemanticFileSearch(tmp_path / "index.json")
    search.record_open(target)

    result = search.search("PDF about Greece used last week", roots=[documents])

    assert result["matches"][0]["name"] == "Greece.pdf"
    assert result["matches"][0]["last_opened_at"]
