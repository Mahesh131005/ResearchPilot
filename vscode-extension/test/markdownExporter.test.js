const { describe, it } = require("node:test");
const assert = require("node:assert");
const { formatReportAsMarkdown } = require("../src/utils/markdownExporter");

describe("MarkdownExporter Tests", () => {
  const sampleReport = {
    title: "Strategic Analysis: Generative AI in Banking",
    executive_summary: "Generative AI has transitioned from exploratory pilots to mission-critical infrastructure.",
    industry_overview: "Commercial banks are deploying LLMs for AML and fraud assessment.",
    key_findings: [
      "Fraud detection response latency reduced by 40% [Doc: bank_report.pdf, Page 1].",
      "Reserve Bank of India mandates explainability [1].",
    ],
    claims: [
      {
        claim_text: "AI models reduce AML false positive alerts by 40%.",
        verification_status: "supported",
        confidence_score: 0.94,
        evidence_quote: "False positives dropped by 40% across commercial lenders.",
        citation_source: "bank_report.pdf (Page 1)",
      },
      {
        claim_text: "100% of human tellers will be eliminated by 2026.",
        verification_status: "contradictory",
        confidence_score: 0.88,
        evidence_quote: "Human staff are transitioning to supervisory oversight roles.",
        citation_source: "Reuters Banking Survey",
      },
    ],
    contradictory_findings: [
      "Total workforce elimination is contradicted by survey data showing job augmentation.",
    ],
    opportunities: ["Automated customer KYC verification."],
    risks_and_challenges: ["Third-party cloud concentration risk."],
    future_outlook: "Widespread hybrid core banking integration expected over next 3 years.",
    references: [
      {
        citation_label: "[1]",
        source_type: "web",
        title: "RBI AI Guidelines",
        url: "https://rbi.org.in/ai-guidelines",
        snippet: "Directives on algorithmic risk management.",
      },
      {
        citation_label: "[Doc: bank_report.pdf, Page 1]",
        source_type: "document",
        title: "bank_report.pdf",
        page_number: 1,
        snippet: "Documented 40% drop in false positive rates.",
      },
    ],
  };

  it("should format all report sections cleanly into Markdown", () => {
    const md = formatReportAsMarkdown(sampleReport, "AI in Banking");

    // Check title & query
    assert.match(md, /# Strategic Analysis: Generative AI in Banking/);
    assert.match(md, /Research Query:\*\* \*AI in Banking\*/);

    // Check sections
    assert.match(md, /## Executive Summary/);
    assert.match(md, /Generative AI has transitioned/);

    assert.match(md, /## Key Research Discoveries/);
    assert.match(md, /Fraud detection response latency/);

    assert.match(md, /## Fact-Checked Claims Audit/);
    assert.match(md, /\| AI models reduce AML false positive alerts by 40%\. \| \*\*SUPPORTED\*\* \| 94% \|/);
    assert.match(md, /\| 100% of human tellers will be eliminated by 2026\. \| \*\*CONTRADICTORY\*\* \| 88% \|/);

    assert.match(md, /## Contradictory Findings & Discrepancies/);
    assert.match(md, /Total workforce elimination is contradicted/);

    assert.match(md, /## Strategic Opportunities/);
    assert.match(md, /Automated customer KYC/);

    assert.match(md, /## Risks, Vulnerabilities & Challenges/);
    assert.match(md, /Third-party cloud concentration/);

    assert.match(md, /## Verified Sources & Provenance/);
    assert.match(md, /\[1\] \*\*RBI AI Guidelines\*\* — \[https:\/\/rbi\.org\.in\/ai-guidelines\]/);
    assert.match(md, /\[Doc: bank_report\.pdf, Page 1\] \*\*bank_report\.pdf\*\* \(Page 1\)/);
  });

  it("should handle empty or null report gracefully", () => {
    const md = formatReportAsMarkdown(null);
    assert.match(md, /No report content available/);
  });
});
