from typing import Dict, Any, Optional
from app.providers.base import LLMProvider
from app.providers.factory import get_llm_provider
from app.schemas.research import ResearchPlan, SubQuestion

PLANNER_SYSTEM_PROMPT = (
    "You are ResearchPilot's Lead Research Planner. Your objective is to deconstruct complex research "
    "questions into a comprehensive, multi-dimensional investigation plan with strict empirical coverage.\n\n"
    "CRITICAL PLANNING RULES:\n"
    "1. BASELINE & BENCHMARK COVERAGE: Identify EVERY algorithm, baseline, benchmark, or comparative method "
    "explicitly named in the user query (e.g., 'LP-based sequential heuristic', 'standard ALNS', 'MA-ALNS'). "
    "You MUST generate dedicated sub-questions that specifically investigate each named baseline and compare it "
    "against the proposed method across cost, efficiency, replication, and runtime.\n"
    "2. EMPIRICAL & STATISTICAL RIGOR: Include sub-questions addressing statistical validation, significance testing, "
    "sample size, and practical trade-offs (e.g. VNF consolidation vs link routing cost, runtime scalability).\n"
    "3. TARGETED SCOPE: Formulate 3 to 5 targeted sub-questions that together cover:\n"
    "   - Algorithmic mechanics and feasibility constraints.\n"
    "   - Head-to-head empirical comparison against EVERY named baseline.\n"
    "   - Statistical significance, ablation studies, and operator impact.\n"
    "   - Practical deployment overheads, runtime scalability, and limitations.\n"
    "4. SOURCE TYPE: Specify the appropriate source type ('web', 'document', or 'both') based on where evidence is most credible.\n"
    "5. SEARCH QUERY REFORMULATION: For each sub-question, provide an optimized `search_query` containing 3 to 6 targeted "
    "keywords (omitting conversational fluff, punctuation, and question marks) to maximize retrieval precision in web search and semantic vector databases.\n"
    "6. Keep objectives concise, action-oriented, and centered on verifiable evidence."
)

class PlannerAgent:
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm = llm_provider or get_llm_provider()

    async def plan(self, query: str, depth: str = "standard") -> ResearchPlan:
        prompt = (
            f"User Research Query: \"{query}\"\n"
            f"Target Depth: {depth}\n\n"
            f"Create a structured research plan breaking down this topic into specific investigation sub-questions."
        )

        try:
            plan = await self.llm.generate_structured(
                prompt=prompt,
                schema=ResearchPlan,
                system_instruction=PLANNER_SYSTEM_PROMPT,
                temperature=0.2,
            )
            return plan
        except Exception as e:
            # In live mode, propagate API/authentication errors rather than silently generating mock responses
            if getattr(self.llm, "is_live", False):
                raise e
            return self._fallback_plan(query)

    def _fallback_plan(self, query: str) -> ResearchPlan:
        """Fallback deterministic plan generation for mock mode."""
        return ResearchPlan(
            title=f"[MOCK] Strategic Research Report: {query[:60]}",
            overview=f"SIMULATED MOCK RESEARCH PLAN: Comprehensive multi-agent investigation into '{query}'.",
            objectives=[
                "Assess baseline technological trends and current industry adoption.",
                "Identify regulatory, security, and compliance frameworks.",
                "Analyze market impact, economic opportunities, and risk factors.",
                "Synthesize 5-year outlook and contradictory viewpoints."
            ],
            sub_questions=[
                SubQuestion(
                    id="sq-1",
                    question=f"What are the foundational trends and current adoption state regarding {query}?",
                    focus_area="Technology & Adoption",
                    source_type="both",
                    search_query=f"{query} technological trends enterprise adoption",
                ),
                SubQuestion(
                    id="sq-2",
                    question=f"What regulatory guidelines, compliance requirements, and risks govern {query}?",
                    focus_area="Regulation & Risk",
                    source_type="both",
                    search_query=f"{query} regulatory compliance guidelines risk frameworks",
                ),
                SubQuestion(
                    id="sq-3",
                    question=f"What are the economic opportunities, challenges, and contradictory findings regarding {query}?",
                    focus_area="Market Impact",
                    source_type="web",
                    search_query=f"{query} market opportunities economic impact challenges",
                )
            ]
        )

