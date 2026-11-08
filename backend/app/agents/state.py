import operator
from typing import TypedDict, Annotated, List, Dict, Any, Optional
from typing_extensions import NotRequired

class ResearchState(TypedDict):
    """LangGraph workflow state for ResearchPilot multi-agent orchestration."""
    job_id: str
    user_id: NotRequired[Optional[str]]
    query: str
    depth: str
    enable_web: bool
    enable_documents: bool
    document_ids: List[str]
    max_tavily_searches: Optional[int]

    # Agent 1 Output
    plan: Optional[Dict[str, Any]]

    # Parallel Research Outputs
    web_evidence: List[Dict[str, Any]]
    document_evidence: List[Dict[str, Any]]

    # Combined & Normalized Evidence
    normalized_evidence: List[Dict[str, Any]]

    # Agent 4 Output: Fact Checking
    fact_checked_claims: List[Dict[str, Any]]

    # Agent 5 Output: Final Structured Report
    report: Optional[Dict[str, Any]]

    # Granular execution milestones (aggregated across parallel branches)
    events: Annotated[List[Dict[str, Any]], operator.add]

    # Error tracking
    error: Optional[str]
