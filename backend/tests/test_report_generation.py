import pytest
import io
import asyncio
from app.agents.fact_checker import FactCheckerAgent
from app.agents.report_writer import ReportWriterAgent
from app.schemas.report import FactCheckedClaim, ResearchReportSchema

@pytest.mark.asyncio
async def test_fact_checker_agent():
    fact_checker = FactCheckerAgent()
    evidence = [
        {
            "id": "ev-1",
            "source_type": "document",
            "title": "banking_guidelines.pdf",
            "page_number": 2,
            "content": "The Reserve Bank of India has issued directives mandating algorithmic governance, explainability, and data localization for all commercial banks.",
            "url": None
        },
        {
            "id": "ev-2",
            "source_type": "web",
            "title": "Reuters Banking AI",
            "page_number": None,
            "content": "A survey of 45 Indian private lenders showed 60% are deploying generative AI in customer service and risk management.",
            "url": "https://www.reuters.com/business/finance/indian-banks-ai"
        }
    ]

    claims = await fact_checker.verify_evidence("Regulatory and market trends in Indian banking", evidence)

    assert len(claims) >= 2
    # Verify claims have required fields
    for c in claims:
        assert isinstance(c, FactCheckedClaim)
        assert c.verification_status in ["supported", "partially_supported", "unsupported", "contradictory"]
        assert 0.0 <= c.confidence_score <= 1.0
        assert len(c.reasoning) > 5

@pytest.mark.asyncio
async def test_report_writer_agent():
    report_writer = ReportWriterAgent()
    evidence = [
        {
            "id": "ev-1",
            "source_type": "document",
            "title": "indian_banking_report.pdf",
            "page_number": 1,
            "content": "Generative AI is accelerating automation in retail banking underwriting.",
            "url": None
        }
    ]
    claims = [
        FactCheckedClaim(
            claim_text="Generative AI is accelerating automation in banking underwriting.",
            verification_status="supported",
            confidence_score=0.92,
            evidence_quote="Generative AI is accelerating automation...",
            citation_source="indian_banking_report.pdf (Page 1)",
            reasoning="Directly supported by the document.",
        )
    ]

    report = await report_writer.write_report(
        query="Analyse Generative AI in Banking",
        plan=None,
        evidence_items=evidence,
        claims=claims,
    )

    assert isinstance(report, ResearchReportSchema)
    # Verify all mandatory sections exist
    assert len(report.title) > 5
    assert len(report.executive_summary) > 20
    assert len(report.industry_overview) > 20
    assert len(report.key_findings) > 0
    assert len(report.opportunities) > 0
    assert len(report.risks_and_challenges) > 0
    assert len(report.contradictory_findings) > 0
    assert len(report.future_outlook) > 10
    assert len(report.claims) > 0
    assert len(report.references) > 0

@pytest.mark.asyncio
async def test_end_to_end_research_report_api(auth_client, sample_pdf_bytes):
    # 1. Upload sample PDF
    files = {
        "file": ("stage4_test_doc.pdf", io.BytesIO(sample_pdf_bytes), "application/pdf")
    }
    upload_res = await auth_client.post("/api/v1/documents/upload", files=files)
    assert upload_res.status_code == 201
    doc_id = upload_res.json()["id"]

    try:
        # 2. Trigger multi-agent research job
        job_req = {
            "query": "Impact of Generative AI on Indian banking operations and RBI guidelines",
            "depth": "standard",
            "enable_web": True,
            "enable_documents": True,
            "document_ids": [doc_id]
        }
        res = await auth_client.post("/api/v1/research/jobs", json=job_req)
        assert res.status_code == 201
        job_id = res.json()["id"]

        # 3. Poll for completion (background asyncio task)
        for _ in range(20):
            await asyncio.sleep(0.5)
            status_res = await auth_client.get(f"/api/v1/research/jobs/{job_id}")
            if status_res.json()["status"] in ["completed", "failed"]:
                break

        assert status_res.json()["status"] == "completed"

        # 4. Get completed report
        report_res = await auth_client.get(f"/api/v1/research/jobs/{job_id}/report")
        assert report_res.status_code == 200
        report = report_res.json()

        # Validate complete required structure
        assert "title" in report
        assert "executive_summary" in report
        assert "industry_overview" in report
        assert "key_findings" in report
        assert "opportunities" in report
        assert "risks_and_challenges" in report
        assert "contradictory_findings" in report
        assert "future_outlook" in report
        assert "claims" in report
        assert "references" in report

        # Verify claims verification statuses
        claim_statuses = [c["verification_status"] for c in report["claims"]]
        assert "supported" in claim_statuses

        # Verify references include document page references
        doc_refs = [r for r in report["references"] if r["source_type"] == "document"]
        assert len(doc_refs) > 0
        assert doc_refs[0]["page_number"] in [1, 2]

        # 5. Download and validate PDF report stream
        pdf_res = await auth_client.get(f"/api/v1/research/jobs/{job_id}/pdf")
        assert pdf_res.status_code == 200
        assert pdf_res.headers["content-type"] == "application/pdf"
        assert "attachment" in pdf_res.headers["content-disposition"]
        assert pdf_res.content.startswith(b"%PDF-")
        assert len(pdf_res.content) > 1000

    finally:
        await auth_client.delete(f"/api/v1/documents/{doc_id}")

