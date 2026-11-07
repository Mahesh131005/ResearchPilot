import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import { documentApi, researchApi } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  FileText,
  Database,
  ArrowRight,
  CheckCircle2,
  Clock,
  UploadCloud,
  AlertCircle,
  Compass,
  PlusCircle,
  Bot,
} from "lucide-react";

export function Dashboard() {
  const [documents, setDocuments] = useState([]);
  const [jobs, setJobs] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchData();
  }, []);

  const fetchData = async () => {
    try {
      setLoading(true);
      setError(null);
      const [docs, researchJobs] = await Promise.all([
        documentApi.list(),
        researchApi.listJobs(),
      ]);
      setDocuments(docs || []);
      setJobs(researchJobs || []);
    } catch (err) {
      console.error("Failed to load dashboard data", err);
      setError("Unable to connect to backend server. Make sure FastAPI is running.");
    } finally {
      setLoading(false);
    }
  };

  const processedCount = documents.filter((d) => d.status === "completed").length;
  const totalChunks = documents.reduce((acc, curr) => acc + (curr.total_chunks || 0), 0);
  const completedJobs = jobs.filter((j) => j.status === "completed").length;

  return (
    <div className="container py-8 space-y-8 px-6 max-w-7xl">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Dashboard</h1>
          <p className="text-muted-foreground mt-1">
            Overview of your research intelligence platform, active agents, and document knowledge base.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Link to="/knowledge-base">
            <Button variant="outline" className="gap-2">
              <UploadCloud className="h-4 w-4" />
              Upload PDFs
            </Button>
          </Link>
          <Link to="/research/new">
            <Button className="gap-2 shadow-sm">
              <PlusCircle className="h-4 w-4" />
              New Research Job
            </Button>
          </Link>
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-3">
          <AlertCircle className="h-5 w-5 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Metrics Row */}
      <div className="grid gap-6 sm:grid-cols-2 lg:grid-cols-4">
        <Card className="shadow-sm border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Research Inquiries</CardTitle>
            <Compass className="h-4 w-4 text-primary" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{loading ? "..." : jobs.length}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {completedJobs} completed investigations
            </p>
          </CardContent>
        </Card>

        <Card className="shadow-sm border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Knowledge Base PDFs</CardTitle>
            <FileText className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{loading ? "..." : documents.length}</div>
            <p className="text-xs text-muted-foreground mt-1">
              {processedCount} parsed and indexed into RAG
            </p>
          </CardContent>
        </Card>

        <Card className="shadow-sm border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Vector Knowledge Chunks</CardTitle>
            <Database className="h-4 w-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold">{loading ? "..." : totalChunks}</div>
            <p className="text-xs text-muted-foreground mt-1">
              Embedded with exact page references
            </p>
          </CardContent>
        </Card>

        <Card className="shadow-sm border">
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <CardTitle className="text-sm font-medium">Multi-Agent Engine</CardTitle>
            <Bot className="h-4 w-4 text-emerald-500" />
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">LangGraph</div>
            <p className="text-xs text-muted-foreground mt-1">
              Planner, Web, Document, Fact Checker
            </p>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        {/* Recent Research Jobs */}
        <Card className="shadow-sm border">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Recent Research Inquiries</CardTitle>
              <CardDescription>Multi-agent research pipelines executed.</CardDescription>
            </div>
            <Link to="/research/new">
              <Button variant="ghost" size="sm" className="gap-1 text-sm">
                New <PlusCircle className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="py-8 text-center text-sm text-muted-foreground">Loading jobs...</div>
            ) : jobs.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <Compass className="h-8 w-8 text-muted-foreground/40 mb-2" />
                <p className="text-sm font-medium text-foreground">No research jobs yet</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Launch your first research inquiry to coordinate specialized agents.
                </p>
                <Link to="/research/new" className="mt-3">
                  <Button size="sm" variant="outline" className="gap-1.5">
                    <PlusCircle className="h-3.5 w-3.5" /> Launch Research
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {jobs.slice(0, 5).map((j) => (
                  <Link
                    key={j.id}
                    to={`/research/${j.id}`}
                    className="flex items-center justify-between p-3 rounded-lg border bg-card/50 hover:bg-muted/40 transition-colors block"
                  >
                    <div className="min-w-0 pr-3">
                      <p className="text-sm font-medium truncate text-foreground">{j.query}</p>
                      <p className="text-xs text-muted-foreground">
                        {new Date(j.created_at).toLocaleDateString()} • Depth: {j.depth}
                      </p>
                    </div>
                    <div className="flex items-center gap-2 flex-shrink-0">
                      {j.status === "completed" && (
                        <Badge variant="success" className="capitalize text-[11px]">
                          Completed
                        </Badge>
                      )}
                      {j.status === "processing" && (
                        <Badge variant="warning" className="capitalize text-[11px] animate-pulse">
                          Running
                        </Badge>
                      )}
                      {j.status === "failed" && (
                        <Badge variant="destructive" className="capitalize text-[11px]">
                          Failed
                        </Badge>
                      )}
                      <ArrowRight className="h-3.5 w-3.5 text-muted-foreground" />
                    </div>
                  </Link>
                ))}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Recent Knowledge Base Documents */}
        <Card className="shadow-sm border">
          <CardHeader className="flex flex-row items-center justify-between">
            <div>
              <CardTitle>Knowledge Base Documents</CardTitle>
              <CardDescription>Recently uploaded PDF sources for RAG.</CardDescription>
            </div>
            <Link to="/knowledge-base">
              <Button variant="ghost" size="sm" className="gap-1 text-sm">
                View all <ArrowRight className="h-3.5 w-3.5" />
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            {loading ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                Loading documents...
              </div>
            ) : documents.length === 0 ? (
              <div className="flex flex-col items-center justify-center py-8 text-center">
                <FileText className="h-8 w-8 text-muted-foreground/40 mb-2" />
                <p className="text-sm font-medium text-foreground">No documents uploaded</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Upload PDF research papers to enable Document RAG search.
                </p>
                <Link to="/knowledge-base" className="mt-3">
                  <Button size="sm" variant="outline" className="gap-1.5">
                    <UploadCloud className="h-3.5 w-3.5" /> Upload PDF
                  </Button>
                </Link>
              </div>
            ) : (
              <div className="space-y-3">
                {documents.slice(0, 5).map((doc) => (
                  <div
                    key={doc.id}
                    className="flex items-center justify-between p-3 rounded-lg border bg-card/50 hover:bg-muted/40 transition-colors"
                  >
                    <div className="flex items-center gap-3 min-w-0">
                      <div className="p-2 rounded bg-primary/10 text-primary flex-shrink-0">
                        <FileText className="h-4 w-4" />
                      </div>
                      <div className="min-w-0">
                        <p className="text-sm font-medium truncate text-foreground">
                          {doc.filename}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {doc.page_count} pages • {doc.total_chunks} chunks
                        </p>
                      </div>
                    </div>
                    <div>
                      {doc.status === "completed" && (
                        <Badge variant="success" className="capitalize text-[11px]">
                          Indexed
                        </Badge>
                      )}
                      {doc.status === "processing" && (
                        <Badge variant="warning" className="capitalize text-[11px] animate-pulse">
                          Processing
                        </Badge>
                      )}
                      {doc.status === "failed" && (
                        <Badge variant="destructive" className="capitalize text-[11px]">
                          Failed
                        </Badge>
                      )}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
