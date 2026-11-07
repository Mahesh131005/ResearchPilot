import uuid
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DocumentQueryRequest(BaseModel):
    query: str = Field(..., min_length=3, description="Research question to query against documents")
    document_id: Optional[uuid.UUID] = Field(None, description="Optional document ID to restrict search to a single PDF")
    top_k: int = Field(5, ge=1, le=20, description="Number of evidence chunks to retrieve")
    threshold: Optional[float] = Field(None, ge=0.0, le=1.0, description="Minimum similarity threshold")

class ChunkEvidence(BaseModel):
    chunk_id: str
    document_id: str
    filename: str
    page_number: int
    chunk_index: int
    content: str
    token_count: int
    similarity_score: float

class Citation(BaseModel):
    document_id: str
    filename: str
    page_number: int
    quote_snippet: Optional[str] = None

class DocumentQueryResponse(BaseModel):
    query: str
    answer: str
    has_sufficient_evidence: bool
    citations: List[Citation] = []
    evidence: List[ChunkEvidence] = []
    model: str = "gemini-2.5-flash"

