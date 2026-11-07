import hashlib
import math
from typing import List, Optional, Type, TypeVar, Any
from pydantic import BaseModel

from app.providers.base import EmbeddingProvider, LLMProvider

T = TypeVar("T", bound=BaseModel)

class MockEmbeddingProvider(EmbeddingProvider):
    """
    Deterministic local embedding provider generating normalized 768-dim vectors
    derived from text token hashes. Perfect for testing and offline demonstration.
    """

    def __init__(self, dim: int = 768):
        self.dim = dim

    @property
    def is_live(self) -> bool:
        return False

    def _hash_text_to_vector(self, text: str) -> List[float]:
        vector = [0.0] * self.dim
        words = text.lower().split()
        if not words:
            return vector

        for word in words:
            # Deterministic MD5 hash to spread across dimensions
            h = hashlib.md5(word.encode("utf-8")).hexdigest()
            idx = int(h[:4], 16) % self.dim
            val = (int(h[4:8], 16) / 65535.0) - 0.5
            vector[idx] += val

        # L2 Normalize
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 0:
            vector = [x / norm for x in vector]
        return vector

    async def embed_documents(self, texts: List[str]) -> List[List[float]]:
        return [self._hash_text_to_vector(t) for t in texts]

    async def embed_query(self, text: str) -> List[float]:
        return self._hash_text_to_vector(text)


class MockLLMProvider(LLMProvider):
    """
    Deterministic mock LLM for testing and demonstrating research workflows
    without consuming API tokens or requiring external internet access.
    Clearly marks all output as simulated/mock.
    """

    @property
    def is_live(self) -> bool:
        return False

    async def generate(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        temperature: float = 0.2,
    ) -> str:
        # Check if context contains text from our sample document
        if "Reserve Bank of India" in prompt or "regulatory" in prompt.lower():
            return (
                "[MOCK SYNTHESIS] According to guidelines from the Reserve Bank of India, financial institutions must prioritize "
                "algorithmic governance, data privacy, and explainability [Page 2]."
            )
        elif "Indian banking" in prompt or "generative" in prompt.lower():
            return (
                "[MOCK SYNTHESIS] Generative AI has transitioned into a strategic driver for Indian banks, powering applications "
                "in fraud detection, automated customer service, and credit evaluation [Page 1]."
            )
        else:
            return "[MOCK SYNTHESIS] Based on the provided document evidence, the topic was analyzed [Page 1]."

    async def generate_structured(
        self,
        prompt: str,
        schema: Type[T],
        system_instruction: Optional[str] = None,
        temperature: float = 0.1,
    ) -> T:
        schema_name = schema.__name__

        # Mock Plan Generation
        if schema_name == "ResearchPlan":
            from app.schemas.research import ResearchPlan, SubQuestion
            return ResearchPlan(
                title=f"[MOCK] Strategic Research Plan: {prompt[:60].strip()}",
                overview="SIMULATED RESEARCH PLAN: Generated using ResearchPilot deterministic mock provider without external LLM calls.",
                objectives=[
                    "[MOCK-OBJ-1] Assess baseline technological trends and current industry adoption.",
                    "[MOCK-OBJ-2] Identify regulatory, security, and compliance frameworks.",
                    "[MOCK-OBJ-3] Analyze market impact, economic opportunities, and risk factors.",
                    "[MOCK-OBJ-4] Synthesize 5-year outlook and contradictory viewpoints."
                ],
                sub_questions=[
                    SubQuestion(
                        id="sq-1",
                        question=f"What are the core technical foundations and adoption metrics regarding {prompt[:40].strip()}?",
                        focus_area="Technology & Adoption",
                        source_type="both"
                    ),
                    SubQuestion(
                        id="sq-2",
                        question="What regulatory, supervisory, and compliance frameworks govern this technology?",
                        focus_area="Regulatory Compliance",
                        source_type="both"
                    ),
                    SubQuestion(
                        id="sq-3",
                        question="What are the key market opportunities, cost savings, and operational risk factors?",
                        focus_area="Market Dynamics & Risk",
                        source_type="both"
                    ),
                    SubQuestion(
                        id="sq-4",
                        question="What are the contradictory viewpoints and 5-year industry projections?",
                        focus_area="Strategic Outlook",
                        source_type="both"
                    ),
                ]
            )

        # Mock Claims Extraction
        elif schema_name == "ClaimsExtractionResult":
            from app.schemas.report import FactCheckedClaim
            from app.agents.fact_checker import ClaimsExtractionResult
            return ClaimsExtractionResult(
                claims=[
                    FactCheckedClaim(
                        claim_text="[MOCK CLAIM 1] Indian scheduled commercial banks are scaling artificial intelligence pilots across credit underwriting and automated compliance.",
                        verification_status="supported",
                        confidence_score=0.92,
                        evidence_quote="Indian scheduled commercial banks are scaling artificial intelligence pilots across credit underwriting, algorithmic compliance monitoring, and customer service automation.",
                        citation_source="[MOCK / FALLBACK WEB SOURCE]",
                        reasoning="Claim directly reflects statements recorded in the collected mock evidence.",
                    ),
                    FactCheckedClaim(
                        claim_text="[MOCK CLAIM 2] Guidelines from the Reserve Bank of India mandate algorithmic governance, customer data privacy, and explainability.",
                        verification_status="supported",
                        confidence_score=0.90,
                        evidence_quote="Guidelines from the Reserve Bank of India mandate algorithmic governance, data privacy, and explainability.",
                        citation_source="[MOCK DOCUMENT Page 2]",
                        reasoning="Corroborated by regulatory whitepaper records.",
                    ),
                    FactCheckedClaim(
                        claim_text="[MOCK CLAIM 3] Generative AI adoption will completely replace 100% of human banking workforce by 2027.",
                        verification_status="unsupported",
                        confidence_score=0.98,
                        reasoning="Evidence does not support full human replacement; sources mandate human-in-the-loop oversight.",
                    ),
                ]
            )

        # Mock Report Generation
        elif schema_name == "ResearchReportSchema":
            from app.schemas.report import ResearchReportSchema, FactCheckedClaim, ReferenceItem
            return ResearchReportSchema(
                title=f"[MOCK REPORT] Research Analysis: {prompt[:60].strip()}",
                executive_summary=(
                    "SIMULATED / MOCK RESEARCH REPORT: This report was synthesized by ResearchPilot's deterministic mock provider "
                    "for demonstration and testing purposes. No live Gemini API tokens were consumed. "
                    "In live mode with valid API keys, this section synthesizes live cross-referenced evidence."
                ),
                industry_overview=(
                    "[MOCK OVERVIEW] The investigated domain is experiencing structural technological shifts. Institutions are transitioning "
                    "from experimental sandboxes to enterprise-grade architectures that integrate LLMs with legacy core systems."
                ),
                key_findings=[
                    "[MOCK FINDING 1] Financial institutions are prioritizing risk detection, automated credit underwriting, and tier-1 customer engagement.",
                    "[MOCK FINDING 2] Central bank guidelines mandate algorithmic transparency, domestic data localization, and explainability.",
                    "[MOCK FINDING 3] Hybrid human-in-the-loop workflows remain essential to prevent model hallucinations and compliance violations."
                ],
                opportunities=[
                    "[MOCK OPP 1] Turnaround time compression for credit assessments and customer queries.",
                    "[MOCK OPP 2] Real-time AML and fraud anomaly detection across high-volume transaction feeds.",
                    "[MOCK OPP 3] Verified knowledge retrieval pipelines powering automated advisory."
                ],
                risks_and_challenges=[
                    "[MOCK RISK 1] Algorithmic governance and explainability requirements under regulatory directives.",
                    "[MOCK RISK 2] Vendor concentration and cross-border data sovereignty risks.",
                    "[MOCK RISK 3] Integration friction with legacy batch-processing core banking mainframes."
                ],
                contradictory_findings=[
                    "[MOCK CONTRADICTION 1] Vendor projections estimate up to 40% cost reductions, whereas regulatory analyses highlight substantial offsetting compliance and audit overheads.",
                    "[MOCK CONTRADICTION 2] Commercial roadmaps propose autonomous lending, while supervisory directives prohibit automated underwriting without human approval."
                ],
                future_outlook=(
                    "[MOCK OUTLOOK] Over the next 3 to 5 years, adoption will shift toward specialized domain-specific models "
                    "deployed on sovereign private clouds with continuous automated compliance auditing."
                ),
                claims=[],
                references=[]
            )

        # Generic fallback for any other schema
        try:
            return schema()
        except Exception:
            raise NotImplementedError(f"Mock structured generation not configured for schema {schema_name}")
