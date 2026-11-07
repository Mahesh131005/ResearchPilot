import re
from typing import List, Dict, Any

class TextChunker:
    """
    Splits document pages into chunks with configurable token size and overlap,
    preserving exact page numbers and document provenance.
    """

    def __init__(self, chunk_size: int = 800, chunk_overlap: int = 120):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    @staticmethod
    def estimate_tokens(text: str) -> int:
        """Rough token count estimation (~4 characters per token or word-based)."""
        if not text:
            return 0
        words = text.split()
        return max(1, int(len(words) * 1.33))

    def chunk_page_text(self, page_number: int, text: str) -> List[Dict[str, Any]]:
        """
        Splits text belonging to a specific page into overlapping chunks.
        """
        if not text or not text.strip():
            return []

        # Split on paragraphs or double linebreaks first, then sentences
        paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
        if not paragraphs:
            paragraphs = [text.strip()]

        chunks = []
        current_sentences = []
        current_tokens = 0

        # Break paragraphs into sentence units
        sentence_units = []
        for p in paragraphs:
            # Sentence split with punctuation preservation
            sentences = re.split(r"(?<=[.!?])\s+", p)
            for s in sentences:
                s_clean = s.strip()
                if s_clean:
                    sentence_units.append(s_clean)

        if not sentence_units:
            return []

        for unit in sentence_units:
            unit_tokens = self.estimate_tokens(unit)

            # If a single sentence exceeds chunk size, split it into word groups
            if unit_tokens > self.chunk_size:
                words = unit.split()
                step = int(self.chunk_size / 1.33)
                overlap_step = int(self.chunk_overlap / 1.33)
                for i in range(0, len(words), max(1, step - overlap_step)):
                    sub_text = " ".join(words[i:i + step])
                    chunks.append({
                        "page_number": page_number,
                        "content": sub_text,
                        "token_count": self.estimate_tokens(sub_text),
                    })
                continue

            if current_tokens + unit_tokens > self.chunk_size and current_sentences:
                # Emit current chunk
                chunk_text = " ".join(current_sentences)
                chunks.append({
                    "page_number": page_number,
                    "content": chunk_text,
                    "token_count": self.estimate_tokens(chunk_text),
                })

                # Maintain overlap from end of current_sentences
                overlap_tokens = 0
                overlap_sentences = []
                for s in reversed(current_sentences):
                    s_tok = self.estimate_tokens(s)
                    if overlap_tokens + s_tok <= self.chunk_overlap:
                        overlap_sentences.insert(0, s)
                        overlap_tokens += s_tok
                    else:
                        break

                current_sentences = overlap_sentences + [unit]
                current_tokens = sum(self.estimate_tokens(s) for s in current_sentences)
            else:
                current_sentences.append(unit)
                current_tokens += unit_tokens

        # Emit remaining sentences if any
        if current_sentences:
            chunk_text = " ".join(current_sentences)
            chunks.append({
                "page_number": page_number,
                "content": chunk_text,
                "token_count": self.estimate_tokens(chunk_text),
            })

        return chunks

    def chunk_document(self, pages_data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Chunks an entire document across all pages, preserving page provenance.
        """
        all_chunks = []
        chunk_idx = 0

        for page in pages_data:
            page_num = page["page_number"]
            page_text = page["text"]

            page_chunks = self.chunk_page_text(page_num, page_text)
            for c in page_chunks:
                c["chunk_index"] = chunk_idx
                all_chunks.append(c)
                chunk_idx += 1

        return all_chunks

