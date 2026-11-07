import React, { useState, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { researchApi, documentApi, systemApi } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Compass,
  Sparkles,
  Globe,
  FileText,
  Layers,
  ArrowRight,
  AlertCircle,
  HelpCircle,
  Cpu,
} from "lucide-react";

export function NewResearch() {
  const navigate = useNavigate();
  const [query, setQuery] = useState("");
  const [depth, setDepth] = useState("standard");
  const [enableWeb, setEnableWeb] = useState(true);
  const [enableDocs, setEnableDocs] = useState(true);
  const [documents, setDocuments] = useState([]);
  const [selectedDocIds, setSelectedDocIds] = useState([]);
  const [loadingDocs, setLoadingDocs] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState(null);
  const [systemStatus, setSystemStatus] = useState(null);

  useEffect(() => {
    loadDocs();
    systemApi.getStatus()
      .then((data) => setSystemStatus(data))
      .catch((err) => console.error("Failed to load system status", err));
  }, []);

  const loadDocs = async () => {
    try {
      const data = await documentApi.list();
      setDocuments(data || []);
      // Pre-select all completed docs by default
      const completedIds = (data || []).filter((d) => d.status === "completed").map((d) => d.id);
      setSelectedDocIds(completedIds);
    } catch (err) {
      console.error("Failed to load documents", err);
    } finally {
      setLoadingDocs(false);
    }
  };

  const exampleQueries = [
    "Analyse the impact of Generative AI on the Indian banking industry over the next five years.",
    "Evaluate the algorithmic compliance risks and Reserve Bank of India regulatory directives for financial LLMs.",
    "Assess operational resilience and cybersecurity challenges of cloud-native core banking architectures.",
  ];

  const handleDocToggle = (docId) => {
    setSelectedDocIds((prev) =>
      prev.includes(docId) ? prev.filter((id) => id !== docId) : [...prev, docId]
    );
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!query.trim()) return;

    if (!enableWeb && (!enableDocs || selectedDocIds.length === 0)) {
      setError("Please enable at least Web Research or select at least one document for Document Research.");
      return;
    }

    try {
      setSubmitting(true);
      setError(null);
      const res = await researchApi.createJob({
        query: query.trim(),
        depth,
        enable_web: enableWeb,
        enable_documents: enableDocs,
        document_ids: enableDocs ? selectedDocIds : [],
      });
      navigate(`/research/${res.id}`);
    } catch (err) {
      console.error("Failed to create research job", err);
      setError(err.response?.data?.detail || "Failed to initialize multi-agent research workflow.");
      setSubmitting(false);
    }
  };

  return (
    <div className="container py-8 space-y-8 px-6 max-w-4xl">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">Initiate New Research</h1>
        <p className="text-muted-foreground mt-1">
          Configure a multi-agent investigation combining live external web research and document RAG.
        </p>
      </div>

      {systemStatus && (
        systemStatus.effective_mode === "live" ? (
          <div className="rounded-lg border border-emerald-500/20 bg-emerald-500/10 p-4 text-xs text-emerald-800 dark:text-emerald-300 flex items-start gap-2.5">
            <Sparkles className="h-4 w-4 mt-0.5 text-emerald-600 flex-shrink-0" />
            <div>
              <span className="font-semibold">Live AI Integration Active:</span> Connected to Gemini 2.5 Flash and Tavily Search API. Ingested PDFs and web sources will be processed via live remote APIs.
            </div>
          </div>
        ) : (
          <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-4 text-xs text-amber-800 dark:text-amber-300 flex items-start gap-2.5">
            <Cpu className="h-4 w-4 mt-0.5 text-amber-600 flex-shrink-0" />
            <div>
              <span className="font-semibold">Simulated Demonstration Mode (No API Keys Configured):</span> Research jobs will execute using deterministic simulated AI models and verified fallback datasets. To activate live Gemini and Tavily research, add your API keys to <code className="bg-amber-500/20 px-1 py-0.5 rounded font-mono">backend/.env</code>.
            </div>
          </div>
        )
      )}

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* Research Query Card */}
        <Card className="shadow-sm border">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Compass className="h-4 w-4 text-primary" />
              Primary Research Question
            </CardTitle>
            <CardDescription>
              Enter a comprehensive inquiry. The Planner Agent will decompose this into structured sub-questions.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <textarea
              className="w-full min-h-[100px] rounded-md border border-input bg-background p-3 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              placeholder="e.g. Analyse the impact of Generative AI on the Indian banking industry over the next five years."
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              required
            />

            <div>
              <p className="text-xs font-semibold text-muted-foreground mb-2 flex items-center gap-1">
                <Sparkles className="h-3.5 w-3.5 text-primary" /> Example Questions:
              </p>
              <div className="space-y-1.5">
                {exampleQueries.map((ex, idx) => (
                  <button
                    key={idx}
                    type="button"
                    onClick={() => setQuery(ex)}
                    className="text-left text-xs text-muted-foreground hover:text-primary transition block w-full truncate p-1.5 rounded hover:bg-muted/50 border border-transparent hover:border-border"
                  >
                    "{ex}"
                  </button>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>

        {/* Research Depth & Scope */}
        <Card className="shadow-sm border">
          <CardHeader>
            <CardTitle className="text-base">Research Depth</CardTitle>
            <CardDescription>Controls the breadth of investigation and sub-question granularity.</CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-3 gap-3">
              {[
                { id: "quick", label: "Quick", desc: "2 sub-questions • rapid synthesis" },
                { id: "standard", label: "Standard", desc: "3-4 sub-questions • thorough coverage" },
                { id: "deep", label: "Deep", desc: "5+ sub-questions • comprehensive audit" },
              ].map((d) => (
                <div
                  key={d.id}
                  onClick={() => setDepth(d.id)}
                  className={`p-3.5 rounded-lg border text-center cursor-pointer transition ${
                    depth === d.id
                      ? "border-primary bg-primary/5 text-primary font-medium"
                      : "border-border hover:bg-muted/30 text-foreground"
                  }`}
                >
                  <p className="text-sm font-semibold capitalize">{d.label}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{d.desc}</p>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* Source Configuration Card */}
        <Card className="shadow-sm border">
          <CardHeader>
            <CardTitle className="text-base">Evidence Sources</CardTitle>
            <CardDescription>
              Toggle specialized parallel research agents to gather multi-source evidence.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            {/* Web Research Toggle */}
            <div className="flex items-start justify-between p-3.5 rounded-lg border bg-card/60">
              <div className="flex items-start gap-3">
                <div className="p-2 rounded bg-blue-500/10 text-blue-600 mt-0.5">
                  <Globe className="h-4 w-4" />
                </div>
                <div>
                  <p className="text-sm font-medium text-foreground">Web Research Agent</p>
                  <p className="text-xs text-muted-foreground">
                    Searches live external sources via Tavily, collecting verified URLs and publication dates.
                  </p>
                </div>
              </div>
              <input
                type="checkbox"
                checked={enableWeb}
                onChange={(e) => setEnableWeb(e.target.checked)}
                className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary mt-1"
              />
            </div>

            {/* Document RAG Toggle & Selector */}
            <div className="space-y-3">
              <div className="flex items-start justify-between p-3.5 rounded-lg border bg-card/60">
                <div className="flex items-start gap-3">
                  <div className="p-2 rounded bg-purple-500/10 text-purple-600 mt-0.5">
                    <FileText className="h-4 w-4" />
                  </div>
                  <div>
                    <p className="text-sm font-medium text-foreground">Document Research Agent (RAG)</p>
                    <p className="text-xs text-muted-foreground">
                      Retrieves semantic vector chunks from uploaded PDFs with exact page-level citations.
                    </p>
                  </div>
                </div>
                <input
                  type="checkbox"
                  checked={enableDocs}
                  onChange={(e) => setEnableDocs(e.target.checked)}
                  className="h-4 w-4 rounded border-gray-300 text-primary focus:ring-primary mt-1"
                />
              </div>

              {enableDocs && (
                <div className="pl-4 pr-1 space-y-2">
                  <p className="text-xs font-semibold text-muted-foreground">
                    Select Target PDFs ({selectedDocIds.length} of {documents.length} selected):
                  </p>
                  {loadingDocs ? (
                    <p className="text-xs text-muted-foreground">Loading documents...</p>
                  ) : documents.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic">
                      No documents in Knowledge Base. You can upload PDFs in the Knowledge Base tab.
                    </p>
                  ) : (
                    <div className="max-h-48 overflow-y-auto space-y-1.5 border rounded-lg p-2 bg-muted/20">
                      {documents.map((doc) => (
                        <label
                          key={doc.id}
                          className="flex items-center gap-2.5 p-2 rounded hover:bg-muted/40 cursor-pointer text-xs"
                        >
                          <input
                            type="checkbox"
                            checked={selectedDocIds.includes(doc.id)}
                            onChange={() => handleDocToggle(doc.id)}
                            className="rounded border-gray-300 text-primary"
                          />
                          <FileText className="h-3.5 w-3.5 text-primary flex-shrink-0" />
                          <span className="truncate flex-1 font-medium">{doc.filename}</span>
                          <span className="text-muted-foreground text-[10px]">
                            {doc.page_count} pages • {doc.total_chunks} chunks
                          </span>
                        </label>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        <div className="flex justify-end">
          <Button type="submit" size="lg" disabled={submitting || !query.trim()} className="gap-2">
            <Compass className={`h-4 w-4 ${submitting ? "animate-spin" : ""}`} />
            {submitting ? "Initializing Agents..." : "Launch Research Engine"}
          </Button>
        </div>
      </form>
    </div>
  );
}

