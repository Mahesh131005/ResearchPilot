import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { researchApi } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  ExternalLink,
  CheckCircle2,
  AlertTriangle,
  XCircle,
  HelpCircle,
  Download,
  ArrowLeft,
  Sparkles,
  ShieldCheck,
  TrendingUp,
  AlertCircle,
  Layers,
  BookOpen,
  Cpu,
} from "lucide-react";

export function ReportViewer() {
  const { jobId } = useParams();
  const [report, setReport] = useState(null);
  const [job, setJob] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [downloadingPdf, setDownloadingPdf] = useState(false);

  useEffect(() => {
    fetchReport();
  }, [jobId]);

  const fetchReport = async () => {
    try {
      setLoading(true);
      setError(null);
      const [reportData, jobData] = await Promise.all([
        researchApi.getReport(jobId),
        researchApi.getJob(jobId),
      ]);
      setReport(reportData);
      setJob(jobData);
    } catch (err) {
      console.error("Failed to fetch report", err);
      setError(
        err.response?.data?.detail || "Research report is not yet generated or job is still running."
      );
    } finally {
      setLoading(false);
    }
  };

  const exportMarkdown = () => {
    if (!report) return;

    let md = `# ${report.title}\n\n`;
    md += `*Research Query: ${job?.query}*\n\n`;
    md += `## Executive Summary\n${report.executive_summary}\n\n`;
    md += `## Industry Overview\n${report.industry_overview}\n\n`;
    md += `## Key Research Findings\n`;
    report.key_findings?.forEach((kf) => (md += `- ${kf}\n`));
    md += `\n## Opportunities\n`;
    report.opportunities?.forEach((op) => (md += `- ${op}\n`));
    md += `\n## Risks & Challenges\n`;
    report.risks_and_challenges?.forEach((rk) => (md += `- ${rk}\n`));
    md += `\n## Contradictory Findings\n`;
    report.contradictory_findings?.forEach((cf) => (md += `- ${cf}\n`));
    md += `\n## Future Outlook\n${report.future_outlook}\n\n`;
    md += `## Fact-Checked Claims Audit\n`;
    report.claims?.forEach((c) => {
      md += `### ${c.claim_text}\n`;
      md += `- Status: ${c.verification_status.toUpperCase()} (Confidence: ${(c.confidence_score * 100).toFixed(0)}%)\n`;
      md += `- Reasoning: ${c.reasoning}\n`;
      if (c.citation_source) md += `- Source: ${c.citation_source}\n`;
      md += `\n`;
    });
    md += `## References & Evidence\n`;
    report.references?.forEach((r) => {
      md += `- ${r.citation_label} **${r.title}**\n`;
      if (r.url) md += `  URL: ${r.url}\n`;
      if (r.page_number) md += `  Page: ${r.page_number}\n`;
      md += `  Excerpt: "${r.snippet}"\n\n`;
    });

    const blob = new Blob([md], { type: "text/markdown" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `ResearchReport-${jobId.slice(0, 8)}.md`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const downloadPdf = async () => {
    if (!report) return;
    try {
      setDownloadingPdf(true);
      const blob = await researchApi.downloadPdf(jobId);
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `ResearchReport-${jobId.slice(0, 8)}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch (err) {
      console.error("Failed to download PDF", err);
      alert("Failed to download PDF report. Please try again.");
    } finally {
      setDownloadingPdf(false);
    }
  };

  if (loading) {
    return (
      <div className="container py-16 text-center max-w-4xl">
        <Sparkles className="h-8 w-8 text-primary animate-spin mx-auto mb-3" />
        <p className="text-base font-medium">Loading research report...</p>
        <p className="text-xs text-muted-foreground mt-1">
          Retrieving fact-checked claims and evidence references.
        </p>
      </div>
    );
  }

  if (error || !report) {
    return (
      <div className="container py-16 text-center max-w-lg space-y-4">
        <AlertCircle className="h-10 w-10 text-destructive mx-auto" />
        <h2 className="text-xl font-bold">Report Not Available</h2>
        <p className="text-sm text-muted-foreground">{error}</p>
        <div className="pt-2 flex justify-center gap-3">
          <Link to={`/research/${jobId}`}>
            <Button variant="outline" size="sm">
              View Agent Progress
            </Button>
          </Link>
          <Link to="/">
            <Button size="sm">Return to Dashboard</Button>
          </Link>
        </div>
      </div>
    );
  }

  const supportedCount = report.claims?.filter((c) => c.verification_status === "supported").length || 0;
  const partiallyCount = report.claims?.filter((c) => c.verification_status === "partially_supported").length || 0;
  const unsupportedCount = report.claims?.filter((c) => c.verification_status === "unsupported").length || 0;
  const contradictoryCount = report.claims?.filter((c) => c.verification_status === "contradictory").length || 0;

  return (
    <div className="container py-8 space-y-8 px-6 max-w-5xl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-start sm:justify-between gap-4 border-b pb-6">
        <div>
          <Link
            to={`/research/${jobId}`}
            className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground mb-3"
          >
            <ArrowLeft className="h-3.5 w-3.5" /> Back to Agent Execution View
          </Link>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight text-foreground">
            {report.title}
          </h1>
          <p className="text-sm text-muted-foreground mt-1.5 max-w-3xl">
            Inquiry: "{job?.query}"
          </p>
        </div>
        <div className="flex items-center gap-2 flex-shrink-0">
          <Button
            onClick={downloadPdf}
            disabled={downloadingPdf}
            variant="default"
            size="sm"
            className="gap-2 bg-primary hover:bg-primary/90 text-primary-foreground shadow-sm"
          >
            <FileText className="h-4 w-4" />
            {downloadingPdf ? "Generating PDF..." : "Download PDF"}
          </Button>
          <Button onClick={exportMarkdown} variant="outline" size="sm" className="gap-2">
            <Download className="h-4 w-4" /> Export Markdown
          </Button>
        </div>
      </div>

      {/* Mock Mode Disclaimer Banner if applicable */}
      {(report.title?.includes("[MOCK") || report.executive_summary?.includes("SIMULATED")) && (
        <div className="rounded-lg border border-amber-500/30 bg-amber-500/10 p-4 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-3">
          <Cpu className="h-5 w-5 mt-0.5 text-amber-600 flex-shrink-0" />
          <div className="space-y-1">
            <span className="font-bold uppercase tracking-wider text-[11px] block text-amber-700 dark:text-amber-400">
              Simulated / Mock Research Report
            </span>
            <p>
              This report was synthesized using ResearchPilot's deterministic mock provider for testing and demonstration purposes. No live Gemini API tokens or real-time web searches were dispatched. Configure valid API keys in <code className="bg-amber-500/20 px-1 py-0.5 rounded font-mono">backend/.env</code> to generate live intelligence.
            </p>
          </div>
        </div>
      )}

      {/* Verification Audit Banner */}
      <Card className="shadow-sm border bg-muted/20">
        <CardContent className="p-4 flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-center gap-3">
            <div className="p-2 rounded-lg bg-primary/10 text-primary">
              <ShieldCheck className="h-5 w-5" />
            </div>
            <div>
              <p className="text-sm font-semibold">Fact-Check Audit Summary</p>
              <p className="text-xs text-muted-foreground">
                Evidence verified by Fact Checker Agent across {report.references?.length || 0} cross-validated sources.
              </p>
            </div>
          </div>
          <div className="flex items-center gap-2 flex-wrap">
            <Badge variant="success" className="text-xs">
              {supportedCount} Supported
            </Badge>
            {partiallyCount > 0 && (
              <Badge variant="warning" className="text-xs">
                {partiallyCount} Partially Supported
              </Badge>
            )}
            {unsupportedCount > 0 && (
              <Badge variant="destructive" className="text-xs">
                {unsupportedCount} Unsupported
              </Badge>
            )}
            {contradictoryCount > 0 && (
              <Badge variant="secondary" className="text-xs font-bold text-amber-700">
                {contradictoryCount} Contradictory
              </Badge>
            )}
          </div>
        </CardContent>
      </Card>

      {/* 1. Executive Summary */}
      <Card className="shadow-sm border-l-4 border-l-primary">
        <CardHeader>
          <CardTitle className="text-lg flex items-center gap-2">
            <Sparkles className="h-5 w-5 text-primary" />
            Executive Summary
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">
            {report.executive_summary}
          </p>
        </CardContent>
      </Card>

      {/* 2. Industry Overview */}
      <Card className="shadow-sm border">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <BookOpen className="h-4 w-4 text-primary" />
            Industry Overview
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">
            {report.industry_overview}
          </p>
        </CardContent>
      </Card>

      {/* 3. Key Findings */}
      <Card className="shadow-sm border">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <CheckCircle2 className="h-4 w-4 text-emerald-500" />
            Key Research Findings
          </CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="space-y-3">
            {report.key_findings?.map((finding, idx) => (
              <li key={idx} className="flex items-start gap-3 text-sm leading-relaxed">
                <span className="flex h-5 w-5 rounded-full bg-primary/10 text-primary text-xs font-semibold items-center justify-center flex-shrink-0 mt-0.5">
                  {idx + 1}
                </span>
                <span className="text-foreground">{finding}</span>
              </li>
            ))}
          </ul>
        </CardContent>
      </Card>

      {/* Two-column layout for Opportunities and Risks */}
      <div className="grid gap-6 sm:grid-cols-2">
        {/* 4. Opportunities */}
        <Card className="shadow-sm border">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-emerald-600">
              <TrendingUp className="h-4 w-4" />
              Strategic Opportunities
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2.5 text-xs sm:text-sm">
              {report.opportunities?.map((op, idx) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 mt-2 flex-shrink-0" />
                  <span className="text-foreground leading-relaxed">{op}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>

        {/* 5. Risks and Challenges */}
        <Card className="shadow-sm border">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-destructive">
              <AlertTriangle className="h-4 w-4" />
              Risks and Challenges
            </CardTitle>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2.5 text-xs sm:text-sm">
              {report.risks_and_challenges?.map((risk, idx) => (
                <li key={idx} className="flex items-start gap-2.5">
                  <span className="h-1.5 w-1.5 rounded-full bg-destructive mt-2 flex-shrink-0" />
                  <span className="text-foreground leading-relaxed">{risk}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      </div>

      {/* 6. Contradictory Findings */}
      {report.contradictory_findings && report.contradictory_findings.length > 0 && (
        <Card className="shadow-sm border border-amber-500/30 bg-amber-500/5">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2 text-amber-700 dark:text-amber-400">
              <AlertCircle className="h-4 w-4" />
              Contradictory & Discrepant Evidence
            </CardTitle>
            <CardDescription className="text-amber-800/80 dark:text-amber-300/80">
              Divergent findings or conflicting projections identified across sources.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <ul className="space-y-2 text-sm">
              {report.contradictory_findings.map((cf, idx) => (
                <li key={idx} className="flex items-start gap-2.5 text-amber-900 dark:text-amber-200">
                  <span className="h-1.5 w-1.5 rounded-full bg-amber-500 mt-2 flex-shrink-0" />
                  <span className="leading-relaxed">{cf}</span>
                </li>
              ))}
            </ul>
          </CardContent>
        </Card>
      )}

      {/* 7. Future Outlook */}
      <Card className="shadow-sm border">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <TrendingUp className="h-4 w-4 text-primary" />
            Future Outlook (3 to 5 Years)
          </CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">
            {report.future_outlook}
          </p>
        </CardContent>
      </Card>

      {/* 8. Fact-Checked Claims Audit */}
      <Card className="shadow-sm border">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <ShieldCheck className="h-4 w-4 text-primary" />
            Fact-Checked Claims Verification Audit ({report.claims?.length || 0})
          </CardTitle>
          <CardDescription>
            Audit trail matching specific assertions against verified empirical evidence.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {report.claims?.map((claim, idx) => (
            <div
              key={idx}
              className="p-4 rounded-lg border bg-muted/20 space-y-2 text-xs"
            >
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-2">
                <p className="font-semibold text-sm text-foreground">{claim.claim_text}</p>
                <div className="flex items-center gap-2 flex-shrink-0">
                  {claim.verification_status === "supported" && (
                    <Badge variant="success">Supported</Badge>
                  )}
                  {claim.verification_status === "partially_supported" && (
                    <Badge variant="warning">Partially Supported</Badge>
                  )}
                  {claim.verification_status === "unsupported" && (
                    <Badge variant="destructive">Unsupported</Badge>
                  )}
                  {claim.verification_status === "contradictory" && (
                    <Badge variant="secondary" className="font-bold text-amber-700">Contradictory</Badge>
                  )}
                  <span className="text-muted-foreground font-mono">
                    {(claim.confidence_score * 100).toFixed(0)}% conf
                  </span>
                </div>
              </div>
              <p className="text-muted-foreground leading-relaxed">
                <span className="font-semibold text-foreground">Reasoning:</span> {claim.reasoning}
              </p>
              {claim.evidence_quote && (
                <div className="bg-background/80 p-2.5 rounded border text-[11px] font-mono text-muted-foreground">
                  "{claim.evidence_quote}"
                </div>
              )}
              {claim.citation_source && (
                <p className="text-[11px] text-primary font-medium">
                  Source: {claim.citation_source}
                </p>
              )}
            </div>
          ))}
        </CardContent>
      </Card>

      {/* 9. Clickable References and Citations */}
      <Card className="shadow-sm border">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Layers className="h-4 w-4 text-primary" />
            Supporting Evidence & Clickable References ({report.references?.length || 0})
          </CardTitle>
          <CardDescription>
            Verifiable source bibliography with genuine URLs and document page coordinates.
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-3">
          {report.references?.map((ref, idx) => (
            <div
              key={ref.id || idx}
              className="p-3.5 rounded-lg border bg-card hover:bg-muted/30 transition text-xs flex flex-col sm:flex-row sm:items-start justify-between gap-3"
            >
              <div className="space-y-1 min-w-0 flex-1">
                <div className="flex items-center gap-2">
                  <span className="font-bold text-primary">{ref.citation_label}</span>
                  <span className="font-semibold text-foreground truncate">{ref.title}</span>
                  <Badge variant="outline" className="text-[10px] capitalize">
                    {ref.source_type}
                  </Badge>
                </div>
                <p className="text-muted-foreground leading-relaxed line-clamp-2 italic">
                  "{ref.snippet}"
                </p>
              </div>

              <div className="flex items-center gap-2 flex-shrink-0">
                {ref.url && (
                  <a
                    href={ref.url}
                    target="_blank"
                    rel="noopener noreferrer"
                    className="inline-flex items-center gap-1 px-2.5 py-1 rounded bg-secondary text-primary hover:underline text-xs font-medium"
                  >
                    <span>Visit Source</span>
                    <ExternalLink className="h-3 w-3" />
                  </a>
                )}
                {ref.page_number && (
                  <span className="px-2.5 py-1 rounded bg-muted text-muted-foreground text-xs font-mono">
                    Page {ref.page_number}
                  </span>
                )}
              </div>
            </div>
          ))}
        </CardContent>
      </Card>
    </div>
  );
}

