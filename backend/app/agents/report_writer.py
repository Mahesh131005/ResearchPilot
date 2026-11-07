from typing import List, Dict, Any, Optional
from app.providers.base import LLMProvider
from app.providers.factory import get_llm_provider
from app.schemas.report import ResearchReportSchema, FactCheckedClaim, ReferenceItem

REPORT_WRITER_SYSTEM_PROMPT = (
    "You are ResearchPilot's Senior Research Report Writer and Intelligence Synthesizer. "
    "You produce institutional-grade research reports for executives and technical leaders.\n\n"
    "CRITICAL SYNTHESIS INVARIANTS:\n"
    "1. THE FACT CHECKER AUDIT IS STRICTLY BINDING AND AUTHORITATIVE:\n"
    "   You are provided with the authoritative FACT-CHECKED CLAIMS AUDIT produced by the Fact Checker Agent.\n"
    "   Your Executive Summary, Industry Overview, Key Research Findings, and Conclusions MUST 100% ALIGN with this audit.\n"
    "   - SUPPORTED claims: Present as verified findings with citations.\n"
    "   - PARTIALLY SUPPORTED claims: Preserve the exact qualifications and caveats (e.g. 'maintained rather than significantly improved', 'observed in a subset of seeds'). Never present as unqualified established facts.\n"
    "   - CONTRADICTORY claims: You MUST NOT present contradictory claims as established facts in the Executive Summary or Key Findings. Instead, you MUST discuss them in Section 6 ('Contradictory Findings'), explicitly stating why the evidence refutes the assertion.\n"
    "   - UNSUPPORTED claims: Must be stated with an explicit disclosure that empirical evidence is lacking.\n\n"
    "2. STATISTICAL VALIDITY & INCONCLUSIVENESS:\n"
    "   - If paired statistical tests (e.g. Wilcoxon tests) do not reach p < 0.05, or if the evidence states that results are 'statistically inconclusive' or 'must not be described as statistically significant', you MUST state in both the Executive Summary and Key Findings that the observed gains are statistically inconclusive.\n"
    "   - NEVER interpret a p-value of 0 as a literal probability of zero. Preserve reported values with qualification (e.g., 'p reported as 0, likely reflecting rounding or numerical underflow') and cross-check against accompanying text.\n"
    "   - Distinguish practical effect size (e.g., 14.71% VNF instance reduction vs 0.11% link cost change) from statistical significance.\n\n"
    "3. EXHAUSTIVE BASELINE COMPARISON:\n"
    "   - The report MUST address EVERY baseline or comparative algorithm explicitly named in the research inquiry (e.g., LP-based sequential heuristic, standard ALNS, MA-ALNS).\n"
    "   - Provide the specific empirical data comparing the method against each baseline.\n"
    "   - If comparative data for any named baseline is missing or partial in the evidence repository, you MUST explicitly state that the comparison could not be established due to absent evidence. Do NOT invent numbers or silently omit the baseline.\n\n"
    "4. NO DISCORDANCE: The Executive Summary, Key Findings, Contradictory Findings, and Fact-Check Audit must present a single unified, coherent scientific verdict."
)

class ReportWriterAgent:
    def __init__(self, llm_provider: Optional[LLMProvider] = None):
        self.llm = llm_provider or get_llm_provider()

    async def write_report(
        self,
        query: str,
        plan: Optional[Dict[str, Any]],
        evidence_items: List[Dict[str, Any]],
        claims: List[FactCheckedClaim],
    ) -> ResearchReportSchema:
        # Build references list
        references = []
        for idx, ev in enumerate(evidence_items, 1):
            if ev.get("source_type") == "web":
                label = f"[{idx}]"
            else:
                label = f"[Doc: {ev.get('title', 'PDF')}, Page {ev.get('page_number', 1)}]"

            references.append(
                ReferenceItem(
                    id=ev.get("id", str(idx)),
                    source_type=ev.get("source_type", "web"),
                    title=ev.get("title", f"Source {idx}"),
                    citation_label=label,
                    url=ev.get("url"),
                    document_id=ev.get("document_id"),
                    page_number=ev.get("page_number"),
                    snippet=ev.get("content", "")[:250],
                )
            )

        # Build claims context for authoritative conditioning
        claims_text_blocks = []
        contradictory_claims = []
        for c in claims:
            status = c.verification_status.upper()
            block = (
                f"- Assertion: \"{c.claim_text}\"\n"
                f"  Audit Status: {status} (Confidence: {int(c.confidence_score * 100)}%)\n"
                f"  Audit Reasoning: {c.reasoning}\n"
                f"  Evidence Quote: \"{c.evidence_quote or 'N/A'}\"\n"
                f"  Citation Source: {c.citation_source or 'N/A'}"
            )
            claims_text_blocks.append(block)
            if c.verification_status == "contradictory":
                contradictory_claims.append(c)

        claims_context = "\n\n".join(claims_text_blocks) if claims_text_blocks else "No claims audited."

        # Context construction
        ref_context = "\n".join(
            [f"{r.citation_label} {r.title} - {r.url or ''}\nExcerpt: {r.snippet}" for r in references[:18]]
        )

        prompt = (
            f"Research Inquiry: \"{query}\"\n\n"
            f"========================================================================\n"
            f"AUTHORITATIVE FACT-CHECKED CLAIMS AUDIT (STRICTLY BINDING):\n"
            f"========================================================================\n"
            f"{claims_context}\n\n"
            f"========================================================================\n"
            f"VERIFIED EVIDENCE & CITATIONS REPOSITORY:\n"
            f"========================================================================\n"
            f"{ref_context}\n\n"
            f"MANDATORY REPORT INSTRUCTIONS:\n"
            f"1. Executive Summary & Key Findings: Must be strictly grounded in the Fact-Checked Claims Audit above.\n"
            f"   - If statistical significance is marked CONTRADICTORY or inconclusive, state clearly that statistical significance was NOT established.\n"
            f"   - If p=0 is reported, explain it as potential numerical rounding/underflow rather than a true probability of zero.\n"
            f"2. Every baseline named in the inquiry (e.g. LP-based sequential heuristic, standard ALNS, MA-ALNS) must be explicitly compared. If comparative evidence is missing for any baseline, explicitly declare that the comparison could not be established.\n"
            f"3. Contradictory Findings: Must contain all CONTRADICTORY claims from the audit, detailing the conflicting evidence.\n"
            f"4. Opportunities & Risks: Emphasize practical trade-offs (e.g. runtime scaling, VNF consolidation vs link routing overhead).\n\n"
            f"Synthesize the comprehensive, institutional-grade research report adhering strictly to the schema."
        )

        try:
            report = await self.llm.generate_structured(
                prompt=prompt,
                schema=ResearchReportSchema,
                system_instruction=REPORT_WRITER_SYSTEM_PROMPT,
                temperature=0.2,
            )
            # Ensure claims and references are attached
            report.claims = claims
            report.references = references

            # Harmonization Guardrail: Ensure all contradictory claims are preserved in contradictory_findings
            if contradictory_claims:
                existing_cf = report.contradictory_findings or []
                for cc in contradictory_claims:
                    ref_text = f"Audit Contradiction: \"{cc.claim_text}\" — {cc.reasoning}"
                    if not any(cc.claim_text[:25].lower() in cf.lower() for cf in existing_cf):
                        existing_cf.append(ref_text)
                report.contradictory_findings = existing_cf

            return report
        except Exception as e:
            # In live mode, propagate API/authentication errors rather than silently generating mock responses
            if getattr(self.llm, "is_live", False):
                raise e
            return self._fallback_report(query, claims, references)

    def _fallback_report(
        self,
        query: str,
        claims: List[FactCheckedClaim],
        references: List[ReferenceItem],
    ) -> ResearchReportSchema:
        return ResearchReportSchema(
            title=f"[MOCK REPORT] Strategic Analysis: {query}",
            executive_summary=(
                f"SIMULATED / MOCK RESEARCH REPORT: This report was synthesized by ResearchPilot's deterministic mock provider "
                f"for demonstration and testing purposes. No live Gemini API tokens were consumed. "
                f"Empirical context for '{query}' was processed using local hash embeddings and verified baseline industry references."
            ),
            industry_overview=(
                f"The domain surrounding {query} is undergoing structural shifts. Institutions are transitioning from "
                "isolated experimental pilots to enterprise-grade architectures that integrate foundation models with existing core systems."
            ),
            key_findings=[
                "Financial institutions are prioritizing risk detection, automated credit underwriting, and tier-1 customer engagement.",
                "Regulatory bodies (including the Reserve Bank of India) mandate strict algorithmic transparency and customer data protection.",
                "Hybrid human-in-the-loop workflows remain essential to mitigate model hallucinations and compliance violations."
            ],
            opportunities=[
                "Substantial reduction in turnaround time for credit assessments and customer queries.",
                "Proactive, real-time AML and fraud anomaly detection across high-volume transaction feeds.",
                "Hyper-personalized financial advisory powered by verified vector knowledge retrieval."
            ],
            risks_and_challenges=[
                "Algorithmic governance and explainability requirements under central bank supervisory mandates.",
                "Data privacy, sovereignty, and cross-border vendor concentration risks.",
                "Integration friction between modern cloud-based AI pipelines and legacy core banking mainframes."
            ],
            contradictory_findings=[
                "Industry vendor estimates project up to 40% operating cost reductions, whereas regulatory analyses highlight substantial offsetting compliance and auditing overheads.",
                "Some commercial projections anticipate autonomous credit approvals, while supervisory guidelines continue to prohibit automated lending without human review."
            ],
            future_outlook=(
                "Over the next 3 to 5 years, adoption will shift toward specialized, domain-specific SLMs (Small Language Models) "
                "deployed on sovereign private clouds with continuous real-time compliance auditing."
            ),
            claims=claims,
            references=references,
        )

