import pytest
from app.services.chunker import TextChunker

def test_chunker_provenance_and_indexing():
    chunker = TextChunker(chunk_size=50, chunk_overlap=10)
    pages_data = [
        {
            "page_number": 1,
            "text": "First page sentence one about artificial intelligence. First page sentence two about banking in India. "
                    "First page sentence three covering fintech developments and digital currency adoption."
        },
        {
            "page_number": 2,
            "text": "Second page sentence discussing regulations and compliance. Second page sentence covering cybersecurity risk."
        }
    ]

    chunks = chunker.chunk_document(pages_data)
    assert len(chunks) >= 2

    # Verify sequential indexing
    for idx, c in enumerate(chunks):
        assert c["chunk_index"] == idx
        assert "page_number" in c
        assert "content" in c
        assert c["token_count"] > 0

    # Verify page preservation
    page1_chunks = [c for c in chunks if c["page_number"] == 1]
    page2_chunks = [c for c in chunks if c["page_number"] == 2]

    assert len(page1_chunks) > 0
    assert len(page2_chunks) > 0
    assert "artificial intelligence" in page1_chunks[0]["content"]
    assert "cybersecurity" in page2_chunks[-1]["content"]

def test_chunker_empty_input():
    chunker = TextChunker()
    assert chunker.chunk_document([]) == []
    assert chunker.chunk_page_text(1, "") == []
    assert chunker.chunk_page_text(1, "   ") == []

