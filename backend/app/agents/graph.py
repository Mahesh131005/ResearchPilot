import datetime
from typing import Dict, Any, List, Optional
from langgraph.graph import StateGraph, START, END
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.state import ResearchState
from app.agents.planner import PlannerAgent
from app.agents.web_research import WebResearchAgent
from app.agents.document_research import DocumentResearchAgent
from app.agents.fact_checker import FactCheckerAgent
from app.agents.report_writer import ReportWriterAgent

def create_research_graph(db: AsyncSession):
    """
    Constructs the complete 5-Agent LangGraph multi-agent orchestration workflow:
    Planner -> [Web Research || Document Research] -> Evidence Normalizer -> Fact Checker -> Report Writer -> END.
    """
    planner_agent = PlannerAgent()
    web_agent = WebResearchAgent()
    doc_agent = DocumentResearchAgent(db)
    fact_checker_agent = FactCheckerAgent()
    report_writer_agent = ReportWriterAgent()

    # 1. Planner Node
    async def planner_node(state: ResearchState) -> Dict[str, Any]:
        query = state["query"]
        depth = state.get("depth", "standard")
        plan = await planner_agent.plan(query, depth)
        plan_dict = plan.model_dump()

        event = {
            "agent_name": "Planner Agent",
            "event_type": "plan_generated",
            "message": f"Generated structured research plan with {len(plan.sub_questions)} targeted sub-questions.",
            "payload": {"sub_questions": [sq.question for sq in plan.sub_questions]},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        return {
            "plan": plan_dict,
            "events": [event],
        }

    # 2. Web Research Node
    async def web_research_node(state: ResearchState) -> Dict[str, Any]:
        plan = state.get("plan") or {}
        sub_questions = plan.get("sub_questions", [])
        evidence = await web_agent.research(sub_questions)

        event = {
            "agent_name": "Web Research Agent",
            "event_type": "web_research_completed",
            "message": f"Collected and verified {len(evidence)} web evidence sources via Tavily.",
            "payload": {"source_urls": [e.get("url") for e in evidence if e.get("url")]},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        return {
            "web_evidence": evidence,
            "events": [event],
        }

    # 3. Document Research Node
    async def document_research_node(state: ResearchState) -> Dict[str, Any]:
        plan = state.get("plan") or {}
        sub_questions = plan.get("sub_questions", [])
        doc_ids = state.get("document_ids", [])
        evidence = await doc_agent.research(sub_questions, document_ids=doc_ids)

        event = {
            "agent_name": "Document Research Agent",
            "event_type": "document_research_completed",
            "message": f"Retrieved {len(evidence)} semantic chunks from uploaded PDFs with exact page references.",
            "payload": {"chunk_count": len(evidence)},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        return {
            "document_evidence": evidence,
            "events": [event],
        }

    # 4. Evidence Normalizer Node (Fan-in)
    async def evidence_normalizer_node(state: ResearchState) -> Dict[str, Any]:
        web_ev = state.get("web_evidence") or []
        doc_ev = state.get("document_evidence") or []

        combined = web_ev + doc_ev
        combined.sort(key=lambda x: x.get("relevance_score", 0.0), reverse=True)

        event = {
            "agent_name": "Evidence Normalizer",
            "event_type": "evidence_normalized",
            "message": f"Aggregated and normalized {len(combined)} total evidence items ({len(web_ev)} web, {len(doc_ev)} document).",
            "payload": {
                "total_evidence": len(combined),
                "web_count": len(web_ev),
                "doc_count": len(doc_ev),
            },
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        return {
            "normalized_evidence": combined,
            "events": [event],
        }

    # 5. Fact Checker Node
    async def fact_checker_node(state: ResearchState) -> Dict[str, Any]:
        query = state["query"]
        evidence = state.get("normalized_evidence") or []
        claims = await fact_checker_agent.verify_evidence(query, evidence)
        claims_dicts = [c.model_dump() for c in claims]

        supported_count = sum(1 for c in claims if c.verification_status == "supported")
        partially_count = sum(1 for c in claims if c.verification_status == "partially_supported")
        contradictory_count = sum(1 for c in claims if c.verification_status == "contradictory")
        unsupported_count = sum(1 for c in claims if c.verification_status == "unsupported")

        event = {
            "agent_name": "Fact Checker Agent",
            "event_type": "fact_check_completed",
            "message": (
                f"Audited {len(claims)} factual assertions "
                f"({supported_count} supported, {partially_count} partially supported, "
                f"{contradictory_count} contradictory, {unsupported_count} unsupported)."
            ),
            "payload": {
                "claim_count": len(claims),
                "supported": supported_count,
                "partially_supported": partially_count,
                "contradictory": contradictory_count,
                "unsupported": unsupported_count,
            },
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        return {
            "fact_checked_claims": claims_dicts,
            "events": [event],
        }

    # 6. Report Writer Node
    async def report_writer_node(state: ResearchState) -> Dict[str, Any]:
        query = state["query"]
        plan = state.get("plan")
        evidence = state.get("normalized_evidence") or []
        claims_dicts = state.get("fact_checked_claims") or []
        from app.schemas.report import FactCheckedClaim
        claims_objects = [FactCheckedClaim(**c) for c in claims_dicts]

        report = await report_writer_agent.write_report(
            query=query,
            plan=plan,
            evidence_items=evidence,
            claims=claims_objects,
        )

        event = {
            "agent_name": "Report Writer Agent",
            "event_type": "report_completed",
            "message": f"Synthesized institutional research report with {len(report.key_findings)} key findings and {len(report.references)} citations.",
            "payload": {"title": report.title},
            "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
        }

        return {
            "report": report.model_dump(),
            "events": [event],
        }

    # Conditional router after Planner
    def route_research(state: ResearchState) -> List[str]:
        enable_web = state.get("enable_web", True)
        enable_docs = state.get("enable_documents", True)

        destinations = []
        if enable_web:
            destinations.append("web_research")
        if enable_docs:
            destinations.append("document_research")

        if not destinations:
            return ["evidence_normalizer"]
        return destinations

    # Assemble Graph
    builder = StateGraph(ResearchState)

    builder.add_node("planner", planner_node)
    builder.add_node("web_research", web_research_node)
    builder.add_node("document_research", document_research_node)
    builder.add_node("evidence_normalizer", evidence_normalizer_node)
    builder.add_node("fact_checker", fact_checker_node)
    builder.add_node("report_writer", report_writer_node)

    builder.add_edge(START, "planner")

    # Conditional fan-out
    builder.add_conditional_edges(
        "planner",
        route_research,
        ["web_research", "document_research", "evidence_normalizer"]
    )

    # Fan-in to normalizer
    builder.add_edge("web_research", "evidence_normalizer")
    builder.add_edge("document_research", "evidence_normalizer")

    # Linear pipeline for verification & synthesis
    builder.add_edge("evidence_normalizer", "fact_checker")
    builder.add_edge("fact_checker", "report_writer")
    builder.add_edge("report_writer", END)

    return builder.compile()
