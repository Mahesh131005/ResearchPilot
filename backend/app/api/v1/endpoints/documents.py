import os
import uuid
from typing import List
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, status
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db, get_current_active_user
from app.models.research import User
from app.models.document import Document
from app.services.document_service import DocumentService
from app.schemas.document import (
    DocumentResponse,
    DocumentDetailResponse,
    DocumentChunkResponse,
    DocumentStatusResponse,
)
from app.core.usage_context import set_usage_context, clear_usage_context

router = APIRouter(prefix="/documents", tags=["documents"])

@router.post("/upload", response_model=DocumentResponse, status_code=status.HTTP_201_CREATED)
async def upload_document(
    file: UploadFile = File(...),
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Upload a research PDF document.
    Extracts text, metadata, generates token chunks with page references, and persists into DB.
    Bound to the currently authenticated user.
    """
    tok = set_usage_context(user_id=current_user.id)
    try:
        service = DocumentService(db)
        document = await service.create_document(file, user_id=current_user.id)
        doc_dict = await service.get_document(document.id, user_id=current_user.id)
        return doc_dict
    finally:
        clear_usage_context(tok)

@router.get("", response_model=List[DocumentResponse])
async def list_documents(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """List all ingested documents belonging to the authenticated user."""
    service = DocumentService(db)
    return await service.list_documents(user_id=current_user.id)

@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get metadata for a specific document owned by the user. Returns 404 if not found or unowned."""
    service = DocumentService(db)
    doc = await service.get_document(document_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )
    return doc

@router.get("/{document_id}/file")
async def get_raw_document_file(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
):
    """
    Download raw PDF file binary.
    If the file on disk was cleared (e.g. following a container restart on ephemeral storage),
    returns an explicit HTTP 410 Gone error explaining that while the raw binary was purged,
    all parsed chunks and vector embeddings remain fully functional in PostgreSQL.
    """
    doc = await db.get(Document, document_id)
    if not doc or (doc.user_id and doc.user_id != current_user.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )

    if not os.path.exists(doc.file_path):
        raise HTTPException(
            status_code=status.HTTP_410_GONE,
            detail=(
                "Original raw PDF binary is no longer present on ephemeral storage following a container restart. "
                "However, all parsed chunks, text, and vector embeddings remain intact in the database and are fully available for research and Q&A."
            ),
        )

    return FileResponse(
        path=doc.file_path,
        filename=doc.filename,
        media_type="application/pdf",
    )

@router.get("/{document_id}/chunks", response_model=List[DocumentChunkResponse])
async def get_document_chunks(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Get all text chunks and page provenance for a document owned by the user."""
    service = DocumentService(db)
    chunks = await service.get_document_chunks(document_id, user_id=current_user.id)
    if chunks is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )
    return chunks

@router.get("/{document_id}/status", response_model=DocumentStatusResponse)
async def get_document_status(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Check processing status of an uploaded document owned by the user."""
    service = DocumentService(db)
    doc = await service.get_document(document_id, user_id=current_user.id)
    if not doc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )
    return doc

@router.delete("/{document_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_document(
    document_id: uuid.UUID,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db)
):
    """Delete a document and chunks owned by the user. Returns 404 if not found or unowned."""
    service = DocumentService(db)
    deleted = await service.delete_document(document_id, user_id=current_user.id)
    if not deleted:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Document with ID {document_id} not found."
        )
    return None
