import os
import uuid
import shutil
from pathlib import Path
from typing import List, Optional, Tuple, Dict, Any
from fastapi import UploadFile, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, func, delete
from sqlalchemy.orm import selectinload

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.services.pdf_parser import PDFParser, PDFParsingError
from app.services.chunker import TextChunker
from app.providers.factory import get_embedding_provider
from app.providers.base import EmbeddingProvider

class DocumentService:
    def __init__(self, db: AsyncSession, embedding_provider: Optional[EmbeddingProvider] = None):
        self.db = db
        self.parser = PDFParser()
        self.chunker = TextChunker(
            chunk_size=settings.CHUNK_SIZE,
            chunk_overlap=settings.CHUNK_OVERLAP
        )
        self.embedding_provider = embedding_provider or get_embedding_provider()

    async def validate_upload(self, file: UploadFile) -> Tuple[str, int]:
        """Validates file extension and size."""
        if not file.filename:
            raise HTTPException(status_code=400, detail="Filename cannot be empty.")

        ext = Path(file.filename).suffix.lower()
        if ext not in settings.ALLOWED_EXTENSIONS:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported file format '{ext}'. Only PDF documents (.pdf) are allowed."
            )

        content = await file.read()
        file_size = len(content)

        max_size_bytes = settings.MAX_FILE_SIZE_MB * 1024 * 1024
        if file_size > max_size_bytes:
            raise HTTPException(
                status_code=400,
                detail=f"File exceeds maximum allowed size of {settings.MAX_FILE_SIZE_MB}MB."
            )

        if file_size == 0:
            raise HTTPException(status_code=400, detail="Uploaded file is empty (0 bytes).")

        if not content.startswith(b"%PDF-"):
            raise HTTPException(
                status_code=400,
                detail="Invalid PDF format: File must begin with '%PDF-' header."
            )

        await file.seek(0)
        return file.filename, file_size

    async def create_document(self, file: UploadFile) -> Document:
        """Stores physical file and creates document record, extracts text, chunks, and embeds."""
        filename, file_size = await self.validate_upload(file)

        doc_id = uuid.uuid4()
        clean_filename = f"{doc_id.hex}_{Path(filename).name}"
        save_path = Path(settings.UPLOAD_DIR) / clean_filename

        with open(save_path, "wb") as buffer:
            shutil.copyfileobj(file.file, buffer)

        document = Document(
            id=doc_id,
            filename=filename,
            file_path=str(save_path),
            file_size=file_size,
            status="processing"
        )
        self.db.add(document)
        await self.db.commit()
        await self.db.refresh(document)

        try:
            pages_data, metadata = self.parser.extract_text_and_metadata(str(save_path))
            chunks_data = self.chunker.chunk_document(pages_data)

            # Generate embeddings for chunks
            chunk_texts = [c["content"] for c in chunks_data]
            embeddings = []
            if chunk_texts:
                try:
                    embeddings = await self.embedding_provider.embed_documents(chunk_texts)
                except Exception as emb_err:
                    if settings.effective_embedding_mode == "live":
                        raise emb_err
                    embeddings = [None] * len(chunk_texts)

            # Persist chunks with embeddings and exact page references
            for idx, c in enumerate(chunks_data):
                emb = embeddings[idx] if idx < len(embeddings) else None
                chunk = DocumentChunk(
                    id=uuid.uuid4(),
                    document_id=doc_id,
                    chunk_index=c["chunk_index"],
                    content=c["content"],
                    page_number=c["page_number"],
                    token_count=c["token_count"],
                    embedding=emb
                )
                self.db.add(chunk)

            document.page_count = metadata.get("page_count", len(pages_data))
            document.meta_info = metadata
            document.status = "completed"
            await self.db.commit()
            await self.db.refresh(document)

        except (PDFParsingError, Exception) as e:
            document.status = "failed"
            document.error_message = str(e)
            await self.db.commit()
            await self.db.refresh(document)
            raise HTTPException(status_code=422, detail=f"PDF parsing error: {str(e)}")

        return document

    async def list_documents(self) -> List[Dict[str, Any]]:
        """Lists all documents annotated with chunk count."""
        query = (
            select(
                Document,
                func.count(DocumentChunk.id).label("total_chunks")
            )
            .outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
            .group_by(Document.id)
            .order_by(Document.created_at.desc())
        )
        result = await self.db.execute(query)
        rows = result.all()

        output = []
        for doc, total_chunks in rows:
            output.append({
                "id": doc.id,
                "filename": doc.filename,
                "file_size": doc.file_size,
                "page_count": doc.page_count,
                "status": doc.status,
                "total_chunks": total_chunks,
                "error_message": doc.error_message,
                "meta_info": doc.meta_info,
                "created_at": doc.created_at,
                "updated_at": doc.updated_at,
            })
        return output

    async def get_document(self, document_id: uuid.UUID) -> Optional[Dict[str, Any]]:
        """Gets a single document by ID with chunk count."""
        query = (
            select(
                Document,
                func.count(DocumentChunk.id).label("total_chunks")
            )
            .outerjoin(DocumentChunk, Document.id == DocumentChunk.document_id)
            .where(Document.id == document_id)
            .group_by(Document.id)
        )
        result = await self.db.execute(query)
        row = result.first()
        if not row:
            return None
        doc, total_chunks = row
        return {
            "id": doc.id,
            "filename": doc.filename,
            "file_size": doc.file_size,
            "page_count": doc.page_count,
            "status": doc.status,
            "total_chunks": total_chunks,
            "error_message": doc.error_message,
            "meta_info": doc.meta_info,
            "created_at": doc.created_at,
            "updated_at": doc.updated_at,
        }

    async def get_document_chunks(self, document_id: uuid.UUID) -> List[DocumentChunk]:
        """Returns all chunks for a document ordered by index."""
        query = (
            select(DocumentChunk)
            .where(DocumentChunk.document_id == document_id)
            .order_by(DocumentChunk.chunk_index.asc())
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_document(self, document_id: uuid.UUID) -> bool:
        """Deletes a document and its associated physical file and chunks."""
        query = select(Document).where(Document.id == document_id)
        result = await self.db.execute(query)
        doc = result.scalar_one_or_none()
        if not doc:
            return False

        try:
            if os.path.exists(doc.file_path):
                os.remove(doc.file_path)
        except OSError:
            pass

        await self.db.delete(doc)
        await self.db.commit()
        return True
