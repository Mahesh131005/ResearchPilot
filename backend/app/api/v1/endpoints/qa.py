from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.db.session import get_db
from app.services.document_qa_service import DocumentQAService
from app.services.retrieval_service import RetrievalService
from app.schemas.qa import (
    DocumentQueryRequest,
    DocumentQueryResponse,
    ChunkEvidence,
)

router = APIRouter(prefix="/qa", tags=["qa"])

@router.post("/query", response_model=DocumentQueryResponse)
async def query_documents(
    request: DocumentQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Ask a research question against uploaded documents.
    Retrieves top-K semantic chunks from pgvector, preserves page references,
    and returns an answer with page-level citations.
    """
    qa_service = DocumentQAService(db)
    return await qa_service.answer_query(request)

@router.post("/search", response_model=List[ChunkEvidence])
async def search_chunks(
    request: DocumentQueryRequest,
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic vector search endpoint.
    Returns ranked evidence chunks with exact page numbers and similarity scores.
    """
    retrieval_service = RetrievalService(db)
    threshold = request.threshold if request.threshold is not None else 0.0
    results = await retrieval_service.search(
        query=request.query,
        document_id=request.document_id,
        top_k=request.top_k,
        threshold=threshold,
    )
    return [ChunkEvidence(**item) for item in results]

