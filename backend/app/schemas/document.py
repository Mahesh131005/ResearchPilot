import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field

class DocumentBase(BaseModel):
    filename: str
    file_size: int

class DocumentCreate(DocumentBase):
    pass

class DocumentChunkResponse(BaseModel):
    id: uuid.UUID
    document_id: uuid.UUID
    chunk_index: int
    content: str
    page_number: int
    token_count: int
    created_at: datetime

    model_config = {"from_attributes": True}

class DocumentResponse(DocumentBase):
    id: uuid.UUID
    status: str
    page_count: Optional[int] = None
    total_chunks: int = 0
    error_message: Optional[str] = None
    meta_info: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

class DocumentDetailResponse(DocumentResponse):
    chunks: List[DocumentChunkResponse] = []

class DocumentStatusResponse(BaseModel):
    id: uuid.UUID
    status: str
    page_count: Optional[int] = None
    total_chunks: int = 0
    error_message: Optional[str] = None

