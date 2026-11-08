import pytest
import io
import uuid
from app.agents.planner import PlannerAgent
from app.agents.web_research import WebResearchAgent
from app.agents.document_research import DocumentResearchAgent
from app.agents.graph import create_research_graph
from app.agents.state import ResearchState
from app.schemas.research import ResearchPlan

@pytest.mark.asyncio
async def test_planner_agent_output_structure():
    planner = PlannerAgent()
    plan = await planner.plan("Impact of Generative AI on Indian Banking", depth="standard")

    assert isinstance(plan, ResearchPlan)
    assert len(plan.objectives) >= 3
    assert len(plan.sub_questions) >= 2
    for sq in plan.sub_questions:
        assert sq.id.startswith("sq-")
        assert len(sq.question) > 5
        assert sq.source_type in ["web", "document", "both"]

@pytest.mark.asyncio
async def test_web_research_agent():
    web_agent = WebResearchAgent()
    sub_questions = [
        {"id": "sq-1", "question": "Reserve Bank of India AI guidelines", "source_type": "web"}
    ]
    results = await web_agent.research(sub_questions)

    assert len(results) > 0
    top_item = results[0]
    assert top_item["source_type"] == "web"
    assert top_item["url"].startswith("http")
    assert len(top_item["content"]) > 10

@pytest.mark.asyncio
async def test_langgraph_multi_agent_workflow(auth_client, sample_pdf_bytes):
    # 1. Upload a document to have in the knowledge base
    files = {
        "file": ("multi_agent_test.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")
    }
    upload_res = await auth_client.post("/api/v1/documents/upload", files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    try:
        from app.db.session import AsyncSessionLocal

        # 2. Test Parallel Workflow (Web + Documents)
        async with AsyncSessionLocal() as session:
            graph = create_research_graph(session)
            state: ResearchState = {
                "job_id": str(uuid.uuid4()),
                "query": "Assess generative AI in Indian banking and Reserve Bank of India rules",
                "depth": "standard",
                "enable_web": True,
                "enable_documents": True,
                "document_ids": [doc_id],
                "plan": None,
                "web_evidence": [],
                "document_evidence": [],
                "normalized_evidence": [],
                "events": [],
                "error": None,
            }

            final_state = await graph.ainvoke(state)

            # Assert Plan
            assert final_state["plan"] is not None
            assert len(final_state["plan"]["sub_questions"]) >= 2

            # Assert Parallel Evidence Execution
            assert len(final_state["web_evidence"]) > 0
            assert len(final_state["document_evidence"]) > 0

            # Assert Evidence Normalizer
            assert len(final_state["normalized_evidence"]) == len(final_state["web_evidence"]) + len(final_state["document_evidence"])

            # Assert Milestone Events from all agents
            agent_names = [ev["agent_name"] for ev in final_state["events"]]
            assert "Planner Agent" in agent_names
            assert "Web Research Agent" in agent_names
            assert "Document Research Agent" in agent_names
            assert "Evidence Normalizer" in agent_names

        # 3. Test Conditional Routing (Web Disabled -> Skip Web Agent)
        async with AsyncSessionLocal() as session:
            graph = create_research_graph(session)
            state_docs_only: ResearchState = {
                "job_id": str(uuid.uuid4()),
                "query": "Regulatory compliance in banking",
                "depth": "quick",
                "enable_web": False,
                "enable_documents": True,
                "document_ids": [doc_id],
                "plan": None,
                "web_evidence": [],
                "document_evidence": [],
                "normalized_evidence": [],
                "events": [],
                "error": None,
            }

            final_docs_only = await graph.ainvoke(state_docs_only)
            assert len(final_docs_only["web_evidence"]) == 0
            assert len(final_docs_only["document_evidence"]) > 0
            assert len(final_docs_only["normalized_evidence"]) == len(final_docs_only["document_evidence"])

    finally:
        await auth_client.delete(f"/api/v1/documents/{doc_id}")

@pytest.mark.asyncio
async def test_research_job_api_lifecycle(auth_client):
    # Test Job creation API
    payload = {
        "query": "Impact of Generative AI on Indian Banking Sector",
        "depth": "standard",
        "enable_web": True,
        "enable_documents": False,
        "document_ids": []
    }
    create_resp = await auth_client.post("/api/v1/research/jobs", json=payload)
    assert create_resp.status_code == 201
    job = create_resp.json()
    job_id = job["id"]
    assert job["query"] == payload["query"]
    assert job["status"] in ["queued", "processing", "completed"]

    # Test List jobs API
    list_resp = await auth_client.get("/api/v1/research/jobs")
    assert list_resp.status_code == 200
    jobs = list_resp.json()
    assert any(j["id"] == job_id for j in jobs)

    # Test Get single job
    get_resp = await auth_client.get(f"/api/v1/research/jobs/{job_id}")
    assert get_resp.status_code == 200
    assert get_resp.json()["id"] == job_id

