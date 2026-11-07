import pymupdf as fitz
import re
from typing import Dict, Any, List, Tuple
from pathlib import Path

class PDFParsingError(Exception):
    """Raised when PDF extraction fails or file is corrupt."""
    pass

class PDFParser:
    """Extracts text, metadata, and page structure from PDF documents using PyMuPDF."""

    @staticmethod
    def extract_text_and_metadata(file_path: str) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
        """
        Parses a PDF file.
        Returns:
            Tuple of (pages_data, metadata)
            where pages_data is a list of {'page_number': int, 'text': str, 'char_count': int}
        """
        path = Path(file_path)
        if not path.exists():
            raise PDFParsingError(f"File not found: {file_path}")

        try:
            doc = fitz.open(file_path)
        except Exception as e:
            raise PDFParsingError(f"Failed to open PDF document: {str(e)}")

        if not doc.is_pdf:
            doc.close()
            raise PDFParsingError("File is not a valid PDF document.")

        if doc.is_encrypted:
            doc.close()
            raise PDFParsingError("Encrypted or password-protected PDFs are not supported.")

        if len(doc) == 0:
            doc.close()
            raise PDFParsingError("The PDF document contains 0 pages.")

        raw_meta = doc.metadata or {}
        metadata = {
            "title": raw_meta.get("title", "") or path.stem,
            "author": raw_meta.get("author", "") or "Unknown",
            "subject": raw_meta.get("subject", "") or "",
            "creator": raw_meta.get("creator", "") or "",
            "producer": raw_meta.get("producer", "") or "",
            "page_count": len(doc),
        }

        pages_data = []
        for page_idx in range(len(doc)):
            page = doc[page_idx]
            page_num = page_idx + 1 # 1-indexed for provenance
            raw_text = page.get_text("text")

            # Clean up whitespace and control chars while preserving structure
            cleaned_text = re.sub(r"[\x00-\x08\x0b-\x0c\x0e-\x1f]", "", raw_text)
            cleaned_text = re.sub(r"[ \t]+", " ", cleaned_text).strip()

            pages_data.append({
                "page_number": page_num,
                "text": cleaned_text,
                "char_count": len(cleaned_text),
            })

        doc.close()
        return pages_data, metadata
