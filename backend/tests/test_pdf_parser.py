import pytest
import tempfile
import os
from pathlib import Path
from app.services.pdf_parser import PDFParser, PDFParsingError

def test_extract_valid_pdf(sample_pdf_bytes):
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(sample_pdf_bytes)
        tmp_path = tmp.name

    try:
        pages, metadata = PDFParser.extract_text_and_metadata(tmp_path)
        assert len(pages) == 2
        assert pages[0]["page_number"] == 1
        assert "Generative Artificial Intelligence in Indian Banking" in pages[0]["text"]
        assert pages[1]["page_number"] == 2
        assert "Reserve Bank of India" in pages[1]["text"]
        assert metadata["page_count"] == 2
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def test_extract_invalid_pdf():
    with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as tmp:
        tmp.write(b"NOT A REAL PDF FILE CONTENT")
        tmp_path = tmp.name

    try:
        with pytest.raises(PDFParsingError):
            PDFParser.extract_text_and_metadata(tmp_path)
    finally:
        if os.path.exists(tmp_path):
            os.remove(tmp_path)

def test_extract_nonexistent_pdf():
    with pytest.raises(PDFParsingError):
        PDFParser.extract_text_and_metadata("non_existent_file_path.pdf")

