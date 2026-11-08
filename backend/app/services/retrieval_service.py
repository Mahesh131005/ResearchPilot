import uuid
from typing import List, Optional, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_

from app.core.config import settings
from app.models.document import Document, DocumentChunk
from app.providers.base import EmbeddingProvider
from app.providers.factory import get_embedding_provider

class RetrievalService:
    """Performs semantic vector search across document chunks using pgvector."""

    def __init__(
        self,
        db: AsyncSession,
        embedding_provider: Optional[EmbeddingProvider] = None,
    ):
        self.db = db
        self.embedding_provider = embedding_provider or get_embedding_provider()

    async def search(
        self,
        query: str,
        document_id: Optional[uuid.UUID] = None,
        document_ids: Optional[List[uuid.UUID]] = None,
        top_k: int = 5,
        threshold: float = 0.0,
        user_id: Optional[uuid.UUID] = None,
    ) -> List[Dict[str, Any]]:
        """
        Embeds the search query and retrieves the Top-K most relevant chunks using cosine similarity.
        Returns chunk content, exact page number, document filename, and similarity score.
        Enforces user ownership isolation when user_id is provided, and supports single or multi-document scoping.
        """
        if not query or not query.strip():
            return []

        # 1. Generate query embedding
        query_vector = await self.embedding_provider.embed_query(query.strip())

        # 2. Vector similarity using pgvector's cosine_distance
        # cosine similarity = 1 - cosine_distance
        distance_col = DocumentChunk.embedding.cosine_distance(query_vector).label("distance")

        stmt = (
            select(
                DocumentChunk,
                Document.filename.label("document_filename"),
                distance_col
            )
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.embedding.isnot(None))
        )

        if user_id:
            stmt = stmt.where(Document.user_id == user_id)

        if document_ids:
            stmt = stmt.where(DocumentChunk.document_id.in_(document_ids))
        elif document_id:
            stmt = stmt.where(DocumentChunk.document_id == document_id)

        # Order by closest distance (smallest distance = highest similarity)
        stmt = stmt.order_by(distance_col.asc()).limit(top_k)

        result = await self.db.execute(stmt)
        rows = result.all()

        results = []
        for chunk, filename, distance in rows:
            # Cosine similarity score in range [0, 1]
            similarity = 1.0 - float(distance) if distance is not None else 0.0
            if similarity < threshold:
                continue

            results.append({
                "chunk_id": str(chunk.id),
                "document_id": str(chunk.document_id),
                "filename": filename,
                "chunk_index": chunk.chunk_index,
                "page_number": chunk.page_number,
                "content": chunk.content,
                "token_count": chunk.token_count,
                "similarity_score": round(similarity, 4),
            })

        return results

