import uuid
from typing import List, Dict, Any, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.services.retrieval_service import RetrievalService

class DocumentResearchAgent:
    """Specialized agent performing semantic RAG retrieval across uploaded PDFs."""

    def __init__(self, db: AsyncSession, retrieval_service: Optional[RetrievalService] = None):
        self.db = db
        self.retrieval_service = retrieval_service or RetrievalService(db)

    async def research(
        self,
        sub_questions: List[Dict[str, Any]],
        document_ids: Optional[List[str]] = None,
        top_k_per_question: int = 4
    ) -> List[Dict[str, Any]]:
        evidence_items = []
        seen_chunks = set()

        # Parse target document UUIDs if provided
        target_doc_id = None
        if document_ids and len(document_ids) == 1:
            try:
                target_doc_id = uuid.UUID(document_ids[0])
            except ValueError:
                pass

        for sq in sub_questions:
            source_type = sq.get("source_type", "both")
            if source_type not in ["document", "both"]:
                continue

            q_text = sq.get("question", "")
            chunks = await self.retrieval_service.search(
                query=q_text,
                document_id=target_doc_id,
                top_k=top_k_per_question,
                threshold=0.2, # Minimum relevance filter
            )

            for c in chunks:
                chunk_id = c["chunk_id"]
                if chunk_id in seen_chunks:
                    continue
                seen_chunks.add(chunk_id)

                evidence_items.append({
                    "id": str(uuid.uuid4()),
                    "source_type": "document",
                    "title": f"Document: {c['filename']} (Page {c['page_number']})",
                    "content": c["content"],
                    "url": None,
                    "document_id": c["document_id"],
                    "page_number": c["page_number"],
                    "published_date": None,
                    "relevance_score": c["similarity_score"],
                    "sub_question_id": sq.get("id"),
                })

        return evidence_items

