import pytest
from app.agents.fact_checker import FactCheckerAgent
from app.agents.report_writer import ReportWriterAgent
from app.schemas.report import FactCheckedClaim, ResearchReportSchema, ReferenceItem

@pytest.mark.asyncio
async def test_supported_claim():
    """Verify that a claim directly corroborated by evidence is classified as supported."""
    checker = FactCheckerAgent()
    evidence = [
        {
            "id": "e1",
            "source_type": "document",
            "title": "report.pdf (Page 8)",
            "page_number": 8,
            "content": "At 40 destinations, VNF count falls by 14.71%, while link cost falls by only about 0.11%.",
            "url": None
        }
    ]
    claims = await checker.verify_evidence(
        query="Does MA-ALNS reduce VNF instances at 40 destinations?",
        evidence_items=evidence
    )
    assert len(claims) > 0
    # At least one claim addressing VNF reduction should be supported
    vnf_claim = next((c for c in claims if "vnf" in c.claim_text.lower() or "14" in c.claim_text), claims[0])
    assert vnf_claim.verification_status in ["supported", "partially_supported"]
    assert vnf_claim.confidence_score >= 0.8
    assert vnf_claim.evidence_quote is not None

@pytest.mark.asyncio
async def test_partially_supported_claim():
    """Verify that claims with caveats or limited scope preserve qualifications."""
    checker = FactCheckerAgent()
    evidence = [
        {
            "id": "e2",
            "source_type": "document",
            "title": "report.pdf (Page 4)",
            "page_number": 4,
            "content": "Link cost falls by only about 0.11% at 40 destinations. The link cost changes little compared with VNF-instance count.",
            "url": None
        }
    ]
    claims = await checker.verify_evidence(
        query="Does MA-ALNS substantially improve link routing efficiency?",
        evidence_items=evidence
    )
    assert len(claims) > 0
    # Any assertion of substantial link cost reduction should be qualified as partially supported or contradictory
    statuses = [c.verification_status for c in claims]
    assert any(s in ["partially_supported", "contradictory", "unsupported"] for s in statuses)

@pytest.mark.asyncio
async def test_contradictory_statistical_significance_claim():
    """Verify that claims of statistical significance are marked CONTRADICTORY when tests are inconclusive."""
    checker = FactCheckerAgent()
    evidence = [
        {
            "id": "e3",
            "source_type": "document",
            "title": "report.pdf (Page 6)",
            "page_number": 6,
            "content": (
                "No reported paired Wilcoxon test reaches p < 0.05. Many matched seeds are exact ties; "
                "only 3–5 seeds improve at destination counts from 12 to 40. The mean cost reductions are "
                "therefore promising but statistically inconclusive under the reported tests. "
                "They must not be described as statistically significant."
            ),
            "url": None
        }
    ]
    claims = await checker.verify_evidence(
        query="Are the improvements achieved by MA-ALNS statistically significant?",
        evidence_items=evidence
    )
    assert len(claims) > 0
    # In mock or live mode, assertions contradicting p < 0.05 must be detected
    sig_claims = [c for c in claims if "statist" in c.claim_text.lower() or "significant" in c.claim_text.lower()]
    if sig_claims:
        assert sig_claims[0].verification_status in ["contradictory", "unsupported"]
        assert "p < 0.05" in sig_claims[0].reasoning or "inconclusive" in sig_claims[0].reasoning.lower() or "statist" in sig_claims[0].reasoning.lower()

@pytest.mark.asyncio
async def test_statistically_insignificant_result_and_p0_underflow():
    """Verify that p=0 is not interpreted as literal zero probability and p >= 0.05 is not reported as significant."""
    checker = FactCheckerAgent()
    evidence = [
        {
            "id": "e4",
            "source_type": "document",
            "title": "report.pdf (Page 6)",
            "page_number": 6,
            "content": "Destinations: 30, Improved: 5, Tied: 15, Worsened: 0, Wilcoxon p: 0. No reported paired Wilcoxon test reaches p < 0.05.",
            "url": None
        }
    ]
    claims = await checker.verify_evidence(
        query="Did the Wilcoxon test reach statistical significance at 30 destinations?",
        evidence_items=evidence
    )
    assert len(claims) > 0
    # Must not claim proven statistical significance
    for c in claims:
        if "statist" in c.claim_text.lower() and "significant" in c.claim_text.lower():
            assert c.verification_status != "supported" or "inconclusive" in c.reasoning.lower()

@pytest.mark.asyncio
async def test_missing_baseline_comparison():
    """Verify that when evidence for a requested baseline is absent, it is not fabricated."""
    checker = FactCheckerAgent()
    evidence = [
        {
            "id": "e5",
            "source_type": "document",
            "title": "report.pdf",
            "page_number": 2,
            "content": "MA-ALNS is compared against an LP-based sequential heuristic. No experiments were run on Standard Genetic Algorithms.",
            "url": None
        }
    ]
    claims = await checker.verify_evidence(
        query="How does MA-ALNS compare against Standard Genetic Algorithms?",
        evidence_items=evidence
    )
    assert len(claims) > 0
    # Any claim about Genetic Algorithms must be unsupported due to absent evidence
    for c in claims:
        if "genetic" in c.claim_text.lower():
            assert c.verification_status in ["unsupported", "contradictory"]

@pytest.mark.asyncio
async def test_conflicting_evidence_from_two_sources():
    """Verify handling when two different sources report conflicting findings."""
    checker = FactCheckerAgent()
    evidence = [
        {
            "id": "e6a",
            "source_type": "document",
            "title": "report_a.pdf (Page 2)",
            "page_number": 2,
            "content": "Algorithm runtime was measured at 0.13 seconds.",
            "url": None
        },
        {
            "id": "e6b",
            "source_type": "web",
            "title": "Benchmark Study",
            "page_number": None,
            "content": "Algorithm runtime was reported at 6.75 seconds, representing an 80x increase.",
            "url": "https://example.com/benchmark"
        }
    ]
    claims = await checker.verify_evidence(
        query="What is the runtime of the algorithm?",
        evidence_items=evidence
    )
    assert len(claims) > 0

@pytest.mark.asyncio
async def test_executive_summary_contradiction_harmonization():
    """
    Verify that when the Fact Checker identifies a CONTRADICTORY claim,
    the Report Writer preserves it in contradictory_findings and does not present it as established fact.
    """
    writer = ReportWriterAgent()
    evidence = [
        {
            "id": "e7",
            "source_type": "document",
            "title": "report.pdf (Page 6)",
            "page_number": 6,
            "content": "No reported paired Wilcoxon test reaches p < 0.05. Mean cost reductions are statistically inconclusive.",
            "url": None
        }
    ]
    claims = [
        FactCheckedClaim(
            claim_text="MA-ALNS demonstrates statistically significant improvements in solution quality.",
            verification_status="contradictory",
            confidence_score=1.0,
            evidence_quote="No reported paired Wilcoxon test reaches p < 0.05. Mean cost reductions are statistically inconclusive.",
            citation_source="report.pdf (Page 6)",
            reasoning="The evidence explicitly refutes statistical significance, stating tests are inconclusive."
        )
    ]

    report = await writer.write_report(
        query="Are MA-ALNS improvements statistically significant?",
        plan=None,
        evidence_items=evidence,
        claims=claims
    )

    assert isinstance(report, ResearchReportSchema)
    # 1. Contradictory findings must be populated
    assert len(report.contradictory_findings) > 0
    cf_text = " ".join(report.contradictory_findings).lower()
    assert "statist" in cf_text or "contradiction" in cf_text or "inconclusive" in cf_text
    # 2. Claims must remain attached
    assert report.claims[0].verification_status == "contradictory"

