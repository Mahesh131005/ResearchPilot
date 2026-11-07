import uuid
from typing import Optional, List, Dict, Any, Literal
from pydantic import BaseModel, Field

class FactCheckedClaim(BaseModel):
    claim_text: str = Field(..., description="Discrete factual assertion made in the research")
    verification_status: Literal["supported", "partially_supported", "unsupported", "contradictory"] = Field(
        ..., description="Verification status against collected evidence"
    )
    confidence_score: float = Field(..., ge=0.0, le=1.0, description="Confidence in the verification assessment")
    evidence_quote: Optional[str] = Field(None, description="Direct quote from supporting or contradictory evidence")
    citation_source: Optional[str] = Field(None, description="Originating document page or web URL")
    reasoning: str = Field(..., description="Explanation of how the evidence supports or contradicts the claim")

class ReportSection(BaseModel):
    title: str
    content: str
    key_takeaways: List[str] = []

class ReferenceItem(BaseModel):
    id: str
    source_type: Literal["web", "document"]
    title: str
    citation_label: str # e.g. "[1]" or "[Doc: filename.pdf, Page 2]"
    url: Optional[str] = None
    document_id: Optional[str] = None
    page_number: Optional[int] = None
    snippet: str

class ResearchReportSchema(BaseModel):
    title: str = Field(..., description="Formal comprehensive report title")
    executive_summary: str = Field(..., description="High-level synthesis for senior decision-makers")
    industry_overview: str = Field(..., description="Market context, background, and adoption baseline")
    key_findings: List[str] = Field(..., description="Detailed research discoveries with inline citations")
    opportunities: List[str] = Field(..., description="Strategic growth and efficiency opportunities")
    risks_and_challenges: List[str] = Field(..., description="Operational, regulatory, and technological risks")
    contradictory_findings: List[str] = Field(..., description="Discrepancies or conflicting evidence identified across sources")
    future_outlook: str = Field(..., description="Projected trajectory over the next 3 to 5 years")
    claims: List[FactCheckedClaim] = Field(default_factory=list, description="Fact-checked claim audit")
    references: List[ReferenceItem] = Field(default_factory=list, description="Traceable citations and evidence list")

