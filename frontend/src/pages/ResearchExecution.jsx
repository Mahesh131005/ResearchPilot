import React, { useState, useEffect } from "react";
import { useParams, Link } from "react-router-dom";
import { researchApi } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Compass,
  CheckCircle2,
  Clock,
  AlertCircle,
  FileText,
  Globe,
  Layers,
  ArrowRight,
  Sparkles,
  Bot,
} from "lucide-react";

export function ResearchExecution() {
  const { jobId } = useParams();
  const [job, setJob] = useState(null);
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  useEffect(() => {
    fetchJobData();
    const interval = setInterval(() => {
      fetchJobData(false);
    }, 2000);

    return () => clearInterval(interval);
  }, [jobId]);

  const fetchJobData = async (initial = false) => {
    try {
      if (initial) setLoading(true);
      const [jobData, eventsData] = await Promise.all([
        researchApi.getJob(jobId),
        researchApi.getEvents(jobId),
      ]);
      setJob(jobData);
      setEvents(eventsData || []);
    } catch (err) {
      console.error("Failed to fetch job data", err);
      setError("Unable to load research job details.");
    } finally {
      if (initial) setLoading(false);
    }
  };

  const isCompleted = job?.status === "completed";
  const isFailed = job?.status === "failed";
  const isProcessing = job?.status === "processing" || job?.status === "queued";

  // Compute active agent based on events
  const agentNames = events.map((e) => e.agent_name);
  const hasPlan = agentNames.includes("Planner Agent");
  const hasWeb = agentNames.includes("Web Research Agent");
  const hasDoc = agentNames.includes("Document Research Agent");
  const hasNormalizer = agentNames.includes("Evidence Normalizer");

  return (
    <div className="container py-8 space-y-8 px-6 max-w-5xl">
      {/* Top Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <Link to="/" className="text-xs text-muted-foreground hover:text-foreground">
              Dashboard
            </Link>
            <span className="text-xs text-muted-foreground">/</span>
            <span className="text-xs font-medium text-foreground">Execution</span>
          </div>
          <h1 className="text-2xl sm:text-3xl font-bold tracking-tight">Multi-Agent Research</h1>
          <p className="text-muted-foreground text-sm mt-1 max-w-2xl">
            {job?.query}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {isCompleted && (
            <div className="flex items-center gap-2">
              <Link to={`/research/${jobId}/report`}>
                <Button size="sm" className="gap-2 shadow-sm">
                  <FileText className="h-4 w-4" /> View Full Report
                </Button>
              </Link>
              <Badge variant="success" className="px-3 py-1 text-sm gap-1.5">
                <CheckCircle2 className="h-4 w-4" />
                Completed
              </Badge>
            </div>
          )}
          {isProcessing && (
            <Badge variant="warning" className="px-3 py-1 text-sm gap-1.5 animate-pulse">
              <Clock className="h-4 w-4" />
              Agents Executing...
            </Badge>
          )}
          {isFailed && (
            <Badge variant="destructive" className="px-3 py-1 text-sm gap-1.5">
              <AlertCircle className="h-4 w-4" />
              Execution Failed
            </Badge>
          )}
        </div>
      </div>

      {error && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-2">
          <AlertCircle className="h-4 w-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Agent Workflow Stepper */}
      <Card className="shadow-sm border">
        <CardHeader>
          <CardTitle className="text-base flex items-center gap-2">
            <Bot className="h-4 w-4 text-primary" />
            Agent Coordination Pipeline (LangGraph)
          </CardTitle>
          <CardDescription>
            Live state transitions across the specialized intelligence layer.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
            {[
              { name: "Planner Agent", active: hasPlan, icon: Compass, desc: "Decomposes sub-questions" },
              { name: "Web Agent", active: hasWeb, icon: Globe, desc: "Tavily web search" },
              { name: "Document Agent", active: hasDoc, icon: FileText, desc: "pgvector RAG search" },
              { name: "Evidence Normalizer", active: hasNormalizer, icon: Layers, desc: "Harmonizes evidence" },
            ].map((step, idx) => {
              const Icon = step.icon;
              return (
                <div
                  key={idx}
                  className={`p-4 rounded-xl border transition-all ${
                    step.active
                      ? "border-emerald-500/30 bg-emerald-500/5 text-foreground"
                      : isProcessing
                      ? "border-border bg-muted/20 text-muted-foreground opacity-60"
                      : "border-border bg-muted/10 text-muted-foreground opacity-40"
                  }`}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className={`p-2 rounded-lg ${step.active ? "bg-emerald-500/10 text-emerald-600" : "bg-muted text-muted-foreground"}`}>
                      <Icon className="h-4 w-4" />
                    </div>
                    {step.active ? (
                      <CheckCircle2 className="h-4 w-4 text-emerald-500" />
                    ) : (
                      <Clock className="h-3.5 w-3.5 text-muted-foreground" />
                    )}
                  </div>
                  <p className="font-semibold text-sm">{step.name}</p>
                  <p className="text-[11px] text-muted-foreground mt-0.5">{step.desc}</p>
                </div>
              );
            })}
          </div>
        </CardContent>
      </Card>

      {/* Research Plan Breakdown */}
      {job?.plan && (
        <Card className="shadow-sm border">
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Sparkles className="h-4 w-4 text-primary" />
              Generated Research Plan: {job.plan.title}
            </CardTitle>
            <CardDescription>{job.plan.overview}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                Core Objectives:
              </p>
              <ul className="space-y-1.5 list-disc list-inside text-xs text-foreground">
                {job.plan.objectives?.map((obj, i) => (
                  <li key={i}>{obj}</li>
                ))}
              </ul>
            </div>

            <div>
              <p className="text-xs font-semibold text-muted-foreground uppercase tracking-wider mb-2">
                Investigative Sub-Questions:
              </p>
              <div className="space-y-2">
                {job.plan.sub_questions?.map((sq) => (
                  <div
                    key={sq.id}
                    className="p-3 rounded-lg border bg-card/60 flex items-start justify-between gap-4"
                  >
                    <div>
                      <span className="text-[10px] font-mono font-bold text-primary uppercase">
                        {sq.id} • {sq.focus_area}
                      </span>
                      <p className="text-xs font-medium text-foreground mt-0.5">{sq.question}</p>
                    </div>
                    <Badge variant="outline" className="text-[10px] capitalize flex-shrink-0">
                      {sq.source_type}
                    </Badge>
                  </div>
                ))}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Live Agent Event Timeline */}
      <Card className="shadow-sm border">
        <CardHeader>
          <CardTitle className="text-base">Milestone Event Log ({events.length})</CardTitle>
          <CardDescription>
            Chronological log of agent actions, evidence extraction, and graph state updates.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {events.length === 0 ? (
            <p className="text-xs text-muted-foreground py-6 text-center">
              Waiting for initial agent milestone events...
            </p>
          ) : (
            <div className="space-y-3 font-mono text-xs">
              {events.map((ev) => (
                <div
                  key={ev.id}
                  className="p-3 rounded-lg border bg-muted/20 flex flex-col sm:flex-row sm:items-center justify-between gap-2"
                >
                  <div className="flex items-center gap-2">
                    <span className="inline-block px-2 py-0.5 rounded bg-primary/10 text-primary font-semibold text-[11px]">
                      {ev.agent_name}
                    </span>
                    <span className="text-foreground">{ev.message}</span>
                  </div>
                  <span className="text-[10px] text-muted-foreground flex-shrink-0">
                    {new Date(ev.created_at).toLocaleTimeString()}
                  </span>
                </div>
              ))}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
