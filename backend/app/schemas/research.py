import uuid
from datetime import datetime
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class SubQuestion(BaseModel):
    id: str = Field(..., description="Unique sub-question ID (e.g. sq-1)")
    question: str = Field(..., description="Targeted research sub-question")
    focus_area: str = Field(..., description="Core area of inquiry (e.g., technology, regulation, market impact)")
    source_type: Literal["both", "web", "document"] = Field(
        "both", description="Target source category for this sub-question"
    )

class ResearchPlan(BaseModel):
    title: str = Field(..., description="Formal title for the research report")
    overview: str = Field(..., description="Synthesis of the main research intent")
    objectives: List[str] = Field(..., description="List of 3-5 core research goals")
    sub_questions: List[SubQuestion] = Field(..., description="Breakdown of specific sub-questions to investigate")

class EvidenceItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()))
    source_type: Literal["web", "document"]
    title: str
    content: str
    url: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    published_date: Optional[str] = None
    relevance_score: float = 1.0

class ResearchJobCreate(BaseModel):
    query: str = Field(..., min_length=5, description="Main research question")
    depth: Literal["quick", "standard", "deep"] = Field("standard")
    enable_web: bool = Field(True, description="Enable external web research via Tavily")
    enable_documents: bool = Field(True, description="Enable RAG retrieval over uploaded PDFs")
    document_ids: List[uuid.UUID] = Field(default_factory=list, description="Selected documents to include")

class ResearchEventResponse(BaseModel):
    id: uuid.UUID
    job_id: uuid.UUID
    agent_name: str
    event_type: str
    message: str
    payload: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = {"from_attributes": True}

class ResearchJobResponse(BaseModel):
    id: uuid.UUID
    query: str
    depth: str
    status: str
    plan: Optional[Dict[str, Any]] = None
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}

