import re
import uuid
from typing import Optional, List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import SecurityAuditor
from app.services.retrieval_service import RetrievalService
from app.providers.base import LLMProvider, EmbeddingProvider
from app.providers.factory import get_llm_provider, get_embedding_provider
from app.schemas.qa import (
    DocumentQueryRequest,
    DocumentQueryResponse,
    ChunkEvidence,
    Citation,
)

class DocumentQAService:
    """Answers user queries grounded in retrieved document chunks with page citations."""

    def __init__(
        self,
        db: AsyncSession,
        retrieval_service: Optional[RetrievalService] = None,
        llm_provider: Optional[LLMProvider] = None,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.db = db
        emb = embedding_provider or get_embedding_provider()
        self.retrieval_service = retrieval_service or RetrievalService(db, embedding_provider=emb)
        self.llm_provider = llm_provider or get_llm_provider()

    async def answer_query(self, request: DocumentQueryRequest, user_id: Optional[uuid.UUID] = None) -> DocumentQueryResponse:
        threshold = request.threshold if request.threshold is not None else settings.SIMILARITY_THRESHOLD

        # 1. Semantic Retrieval with user isolation
        retrieved_data = await self.retrieval_service.search(
            query=request.query,
            document_id=request.document_id,
            top_k=request.top_k,
            threshold=threshold,
            user_id=user_id,
        )

        evidence_list = [ChunkEvidence(**item) for item in retrieved_data]

        # 2. Check for missing evidence
        if not evidence_list:
            return DocumentQueryResponse(
                query=request.query,
                answer="Insufficient evidence in the uploaded documents to answer this research question. No matching document pages were found above the relevance threshold.",
                has_sufficient_evidence=False,
                citations=[],
                evidence=[],
                model=settings.LLM_MODEL,
            )

        # 3. Construct evidence context with security boundary isolation
        context_blocks = []
        for idx, ev in enumerate(evidence_list, 1):
            source_tag = f"Doc: {ev.filename} (Page {ev.page_number})"
            safe_block = SecurityAuditor.format_safe_context(source_tag, ev.content)
            context_blocks.append(f"[Source #{idx} | {source_tag}]:\n{safe_block}")
        context_str = "\n\n".join(context_blocks)

        # 4. Formulate Prompt
        system_instruction = (
            "You are ResearchPilot's Document Research Specialist. Your job is to answer research questions "
            "strictly and faithfully based on the provided document excerpts.\n\n"
            "CRITICAL INSTRUCTIONS:\n"
            "1. Base your answer ONLY on the provided context. Do NOT extrapolate, speculate, or introduce external knowledge.\n"
            "2. Whenever citing facts, include exact page citations in brackets, for example: [Page 2] or [Page 1].\n"
            "3. If the excerpts only partially address the question, clearly state what is supported and what information is missing.\n"
            "4. If the excerpts contain contradictory statements, highlight the discrepancy."
        )

        prompt = (
            f"Research Question: {request.query}\n\n"
            f"Retrieved Document Evidence:\n"
            f"----------------------------------------\n"
            f"{context_str}\n"
            f"----------------------------------------\n\n"
            f"Synthesize a clear, structured research answer with exact [Page X] citations based strictly on the evidence above."
        )

        # 5. Generate Answer via LLM
        answer = await self.llm_provider.generate(
            prompt=prompt,
            system_instruction=system_instruction,
            temperature=0.1,
        )

        # 6. Extract page citations from answer and match to chunks
        cited_pages = set()
        matches = re.findall(r"\[Page\s*(\d+)\]", answer, re.IGNORECASE)
        for m in matches:
            try:
                cited_pages.add(int(m))
            except ValueError:
                pass

        citations = []
        # Create citations from cited pages that exist in evidence
        for page_num in sorted(cited_pages):
            matching_chunks = [ev for ev in evidence_list if ev.page_number == page_num]
            if matching_chunks:
                first_match = matching_chunks[0]
                citations.append(
                    Citation(
                        document_id=first_match.document_id,
                        filename=first_match.filename,
                        page_number=page_num,
                        quote_snippet=first_match.content[:150] + "...",
                    )
                )

        # If LLM didn't format [Page X] but retrieved chunks exist, attach evidence chunks
        if not citations and evidence_list:
            top_chunk = evidence_list[0]
            citations.append(
                Citation(
                    document_id=top_chunk.document_id,
                    filename=top_chunk.filename,
                    page_number=top_chunk.page_number,
                    quote_snippet=top_chunk.content[:150] + "...",
                )
            )

        return DocumentQueryResponse(
            query=request.query,
            answer=answer.strip(),
            has_sufficient_evidence=True,
            citations=citations,
            evidence=evidence_list,
            model=settings.LLM_MODEL,
        )
