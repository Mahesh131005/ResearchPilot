from typing import List, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select

from app.api.deps import get_db, get_current_active_user
from app.models.research import User
from app.models.document import Document
from app.services.document_qa_service import DocumentQAService
from app.services.retrieval_service import RetrievalService
from app.schemas.qa import (
    DocumentQueryRequest,
    DocumentQueryResponse,
    ChunkEvidence,
)
from app.core.usage_context import set_usage_context, clear_usage_context

router = APIRouter(prefix="/qa", tags=["qa"])

@router.post("/query", response_model=DocumentQueryResponse)
async def query_documents(
    request: DocumentQueryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Ask a research question against uploaded documents owned by the authenticated user.
    Retrieves top-K semantic chunks from pgvector, preserves page references,
    and returns an answer with page-level citations.
    """
    if request.document_id:
        doc_stmt = select(Document.id).where(
            Document.id == request.document_id,
            Document.user_id == current_user.id
        )
        doc_res = await db.execute(doc_stmt)
        if not doc_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {request.document_id} not found."
            )

    tok = set_usage_context(user_id=current_user.id)
    try:
        qa_service = DocumentQAService(db)
        return await qa_service.answer_query(request, user_id=current_user.id)
    finally:
        clear_usage_context(tok)

@router.post("/search", response_model=List[ChunkEvidence])
async def search_chunks(
    request: DocumentQueryRequest,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Semantic vector search endpoint scoped to the authenticated user's documents.
    Returns ranked evidence chunks with exact page numbers and similarity scores.
    """
    if request.document_id:
        doc_stmt = select(Document.id).where(
            Document.id == request.document_id,
            Document.user_id == current_user.id
        )
        doc_res = await db.execute(doc_stmt)
        if not doc_res.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Document with ID {request.document_id} not found."
            )

    tok = set_usage_context(user_id=current_user.id)
    try:
        retrieval_service = RetrievalService(db)
        threshold = request.threshold if request.threshold is not None else 0.0
        results = await retrieval_service.search(
            query=request.query,
            document_id=request.document_id,
            top_k=request.top_k,
            threshold=threshold,
            user_id=current_user.id,
        )
        return [ChunkEvidence(**item) for item in results]
    finally:
        clear_usage_context(tok)
