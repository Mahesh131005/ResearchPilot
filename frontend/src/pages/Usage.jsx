import React, { useState, useEffect } from "react";
import { Link } from "react-router-dom";
import {
  Gauge,
  Calendar,
  Clock,
  Cpu,
  Globe,
  Sparkles,
  AlertTriangle,
  CheckCircle2,
  RefreshCw,
  Shield,
  Layers,
  ChevronLeft,
  ChevronRight,
  Database,
  Info,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { usageApi } from "@/services/api";
import { useAuth } from "@/context/AuthContext";

export function Usage() {
  const { user } = useAuth();
  const [summary, setSummary] = useState(null);
  const [history, setHistory] = useState([]);
  const [historyTotal, setHistoryTotal] = useState(0);
  const [historyPage, setHistoryPage] = useState(1);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [error, setError] = useState(null);

  // Admin stats
  const [adminSummary, setAdminSummary] = useState(null);
  const [adminUsers, setAdminUsers] = useState([]);
  const [activeTab, setActiveTab] = useState("my-usage");

  useEffect(() => {
    loadData();
  }, [historyPage]);

  const loadData = async () => {
    try {
      setRefreshing(true);
      setError(null);
      const [sumData, histData] = await Promise.all([
        usageApi.getMyUsage(),
        usageApi.getMyHistory(historyPage, 15),
      ]);
      setSummary(sumData);
      setHistory(histData.items || []);
      setHistoryTotal(histData.total || 0);

      if (user?.role === "admin") {
        try {
          const [admSum, admUsr] = await Promise.all([
            usageApi.getAdminSummary(),
            usageApi.getAdminUsers(1, 20),
          ]);
          setAdminSummary(admSum);
          setAdminUsers(admUsr.items || []);
        } catch (admErr) {
          console.error("Failed to load admin metrics", admErr);
        }
      }
    } catch (err) {
      console.error("Failed to load usage data", err);
      setError("Unable to load quota usage data. Please try again.");
    } finally {
      setLoading(false);
      setRefreshing(false);
    }
  };

  const formatTokens = (num) => {
    if (!num) return "0";
    if (num >= 1000000) return `${(num / 1000000).toFixed(2)}M`;
    if (num >= 1000) return `${(num / 1000).toFixed(1)}k`;
    return num.toLocaleString();
  };

  const formatDate = (isoString) => {
    if (!isoString) return "-";
    const d = new Date(isoString);
    return d.toLocaleString("en-US", {
      month: "short",
      day: "numeric",
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    });
  };

  const getPercentage = (used, total) => {
    if (!total || total === 0) return 0;
    return Math.min(100, Math.round((used / total) * 100));
  };

  if (loading) {
    return (
      <div className="container py-12 max-w-7xl px-6 flex items-center justify-center min-h-[50vh]">
        <div className="flex flex-col items-center gap-3 text-muted-foreground">
          <RefreshCw className="h-8 w-8 animate-spin text-primary" />
          <p className="text-sm font-medium">Loading real-time quota telemetry...</p>
        </div>
      </div>
    );
  }

  const limits = summary?.limits || {};
  const dailyPct = getPercentage(summary?.daily_jobs_used, limits.daily_jobs_limit);
  const monthlyPct = getPercentage(summary?.monthly_jobs_used, limits.monthly_jobs_limit);
  const hourlyPct = getPercentage(summary?.hourly_submissions_used, limits.hourly_submissions_limit);
  const isDailyExceeded = summary?.daily_jobs_remaining === 0;
  const isConcurrentExceeded = summary?.concurrent_jobs_active >= limits.concurrent_jobs_limit;

  return (
    <div className="container py-8 max-w-7xl px-6 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">Usage Telemetry & Quotas</h1>
            <Badge variant="outline" className="capitalize text-xs font-semibold px-2.5 py-0.5">
              {summary?.tier || "Free"} Tier
            </Badge>
            {user?.role === "admin" && (
              <Badge variant="secondary" className="gap-1 text-xs px-2 py-0.5">
                <Shield className="h-3 w-3 text-primary" /> Admin View
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            Monitor real-time Gemini token expenditure, Tavily search volume, rate limits, and job concurrency.
          </p>
        </div>
        <div className="flex items-center gap-2">
          {user?.role === "admin" && (
            <div className="flex items-center bg-secondary rounded-lg p-1 border">
              <button
                onClick={() => setActiveTab("my-usage")}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  activeTab === "my-usage"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                My Account
              </button>
              <button
                onClick={() => setActiveTab("platform")}
                className={`px-3 py-1.5 rounded-md text-xs font-medium transition-all ${
                  activeTab === "platform"
                    ? "bg-background text-foreground shadow-sm"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                Platform Admin
              </button>
            </div>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={loadData}
            disabled={refreshing}
            className="gap-1.5 shadow-sm"
          >
            <RefreshCw className={`h-4 w-4 ${refreshing ? "animate-spin" : ""}`} />
            <span>Refresh</span>
          </Button>
        </div>
      </div>

      {/* Exceeded Warning Banner */}
      {(isDailyExceeded || isConcurrentExceeded) && (
        <div className="rounded-lg border border-warning/50 bg-warning/10 p-4 flex items-start gap-3 text-warning-foreground">
          <AlertTriangle className="h-5 w-5 text-warning shrink-0 mt-0.5" />
          <div className="space-y-1 text-sm">
            <h4 className="font-semibold text-foreground">Quota Ceiling Reached</h4>
            <p className="text-muted-foreground">
              {isDailyExceeded && (
                <span>
                  You have exhausted your daily limit of {limits.daily_jobs_limit} research jobs. Daily quotas reset at 00:00 UTC.{" "}
                </span>
              )}
              {isConcurrentExceeded && (
                <span>
                  You currently have {summary.concurrent_jobs_active} active job(s) in progress. Your tier allows a maximum of{" "}
                  {limits.concurrent_jobs_limit} concurrent job.
                </span>
              )}
            </p>
          </div>
        </div>
      )}

      {error && (
        <div className="rounded-lg border border-destructive/50 bg-destructive/10 p-4 text-sm text-destructive">
          {error}
        </div>
      )}

      {activeTab === "my-usage" ? (
        <>
          {/* Section 1: Quota Progress Cards */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            {/* Daily Research Jobs */}
            <Card className="shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Daily Jobs Used
                </CardTitle>
                <Calendar className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-baseline justify-between">
                  <div className="text-2xl font-bold tracking-tight">
                    {summary?.daily_jobs_used ?? 0}
                    <span className="text-sm font-normal text-muted-foreground">
                      {" "}/ {limits.daily_jobs_limit ?? 5}
                    </span>
                  </div>
                  <span className="text-xs font-semibold text-muted-foreground">
                    {summary?.daily_jobs_remaining ?? 0} left today
                  </span>
                </div>
                <Progress value={dailyPct} className="h-2" />
                <p className="text-[11px] text-muted-foreground flex items-center justify-between">
                  <span>Resets: 00:00 UTC</span>
                  <span>{dailyPct}% used</span>
                </p>
              </CardContent>
            </Card>

            {/* Monthly Research Jobs */}
            <Card className="shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Monthly Quota
                </CardTitle>
                <Layers className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-baseline justify-between">
                  <div className="text-2xl font-bold tracking-tight">
                    {summary?.monthly_jobs_used ?? 0}
                    <span className="text-sm font-normal text-muted-foreground">
                      {" "}/ {limits.monthly_jobs_limit ?? 100}
                    </span>
                  </div>
                  <span className="text-xs font-semibold text-muted-foreground">
                    {summary?.monthly_jobs_remaining ?? 0} left
                  </span>
                </div>
                <Progress value={monthlyPct} className="h-2" />
                <p className="text-[11px] text-muted-foreground flex items-center justify-between">
                  <span>Monthly allocation</span>
                  <span>{monthlyPct}% used</span>
                </p>
              </CardContent>
            </Card>

            {/* Hourly Rate Limit */}
            <Card className="shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Hourly Submissions
                </CardTitle>
                <Clock className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-baseline justify-between">
                  <div className="text-2xl font-bold tracking-tight">
                    {summary?.hourly_submissions_used ?? 0}
                    <span className="text-sm font-normal text-muted-foreground">
                      {" "}/ {limits.hourly_submissions_limit ?? 5}
                    </span>
                  </div>
                  <Badge variant="outline" className="text-[11px] font-normal">
                    Sliding 60m
                  </Badge>
                </div>
                <Progress value={hourlyPct} className="h-2" />
                <p className="text-[11px] text-muted-foreground flex items-center justify-between">
                  <span>Rate limit window</span>
                  <span>{hourlyPct}% used</span>
                </p>
              </CardContent>
            </Card>

            {/* Concurrency Status */}
            <Card className="shadow-sm">
              <CardHeader className="flex flex-row items-center justify-between pb-2">
                <CardTitle className="text-sm font-medium text-muted-foreground">
                  Active Concurrency
                </CardTitle>
                <Gauge className="h-4 w-4 text-muted-foreground" />
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="flex items-baseline justify-between">
                  <div className="text-2xl font-bold tracking-tight">
                    {summary?.concurrent_jobs_active ?? 0}
                    <span className="text-sm font-normal text-muted-foreground">
                      {" "}/ {limits.concurrent_jobs_limit ?? 1}
                    </span>
                  </div>
                  {summary?.concurrent_jobs_active > 0 ? (
                    <Badge variant="secondary" className="gap-1 text-xs">
                      <span className="h-2 w-2 rounded-full bg-amber-500 animate-pulse" />
                      In Flight
                    </Badge>
                  ) : (
                    <Badge variant="success" className="gap-1 text-xs">
                      <CheckCircle2 className="h-3 w-3" /> Ready
                    </Badge>
                  )}
                </div>
                <div className="h-2 rounded-full bg-secondary overflow-hidden">
                  <div
                    className={`h-full transition-all duration-300 ${
                      isConcurrentExceeded ? "bg-amber-500" : "bg-primary"
                    }`}
                    style={{
                      width: `${Math.min(100, ((summary?.concurrent_jobs_active || 0) / (limits.concurrent_jobs_limit || 1)) * 100)}%`,
                    }}
                  />
                </div>
                <p className="text-[11px] text-muted-foreground">
                  Max parallel agent executions
                </p>
              </CardContent>
            </Card>
          </div>

          {/* Section 2: Provider Telemetry Breakdown */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Gemini Token Consumption */}
            <Card className="shadow-sm">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-md bg-primary/10 text-primary">
                      <Sparkles className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-base">Google Gemini Token Telemetry</CardTitle>
                      <CardDescription className="text-xs">
                        Actual token metadata captured across Planner, Fact Checker, and Report Writer
                      </CardDescription>
                    </div>
                  </div>
                  {summary?.gemini_usage?.has_estimated_usage ? (
                    <Badge variant="outline" className="text-[10px] text-muted-foreground">
                      Includes Simulated Tokens
                    </Badge>
                  ) : (
                    <Badge variant="success" className="text-[10px]">
                      Provider Verified
                    </Badge>
                  )}
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 text-center">
                  <div className="p-3 bg-secondary/50 rounded-lg border">
                    <p className="text-xs text-muted-foreground">Prompt (Input)</p>
                    <p className="text-lg font-bold mt-0.5">
                      {formatTokens(summary?.gemini_usage?.input_tokens)}
                    </p>
                  </div>
                  <div className="p-3 bg-secondary/50 rounded-lg border">
                    <p className="text-xs text-muted-foreground">Output</p>
                    <p className="text-lg font-bold mt-0.5">
                      {formatTokens(summary?.gemini_usage?.output_tokens)}
                    </p>
                  </div>
                  <div className="p-3 bg-secondary/50 rounded-lg border">
                    <p className="text-xs text-muted-foreground">Total LLM</p>
                    <p className="text-lg font-bold mt-0.5 text-primary">
                      {formatTokens(summary?.gemini_usage?.total_tokens)}
                    </p>
                  </div>
                  <div className="p-3 bg-secondary/50 rounded-lg border">
                    <p className="text-xs text-muted-foreground">Embeddings</p>
                    <p className="text-lg font-bold mt-0.5">
                      {formatTokens(summary?.gemini_usage?.embedding_tokens)}
                    </p>
                  </div>
                </div>
                <div className="flex items-center justify-between text-xs text-muted-foreground pt-1 border-t">
                  <span>Total Provider API Invocations</span>
                  <span className="font-semibold text-foreground">
                    {summary?.gemini_usage?.request_count ?? 0} calls
                  </span>
                </div>
              </CardContent>
            </Card>

            {/* Tavily Web Search Volume */}
            <Card className="shadow-sm">
              <CardHeader>
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-2">
                    <div className="p-2 rounded-md bg-blue-500/10 text-blue-500">
                      <Globe className="h-5 w-5" />
                    </div>
                    <div>
                      <CardTitle className="text-base">Tavily Web Search Volume</CardTitle>
                      <CardDescription className="text-xs">
                        Deep web exploration and live evidence discovery calls
                      </CardDescription>
                    </div>
                  </div>
                  <Badge variant="outline" className="text-[10px]">
                    Max {limits.tavily_searches_per_job_limit ?? 5}/job
                  </Badge>
                </div>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3 text-center">
                  <div className="p-4 bg-secondary/50 rounded-lg border">
                    <p className="text-xs text-muted-foreground">Cumulative Search Queries</p>
                    <p className="text-2xl font-bold mt-1 text-primary">
                      {summary?.tavily_usage?.search_count ?? 0}
                    </p>
                  </div>
                  <div className="p-4 bg-secondary/50 rounded-lg border">
                    <p className="text-xs text-muted-foreground">Per-Job Search Ceiling</p>
                    <p className="text-2xl font-bold mt-1">
                      {limits.tavily_searches_per_job_limit ?? 5}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2 text-xs text-muted-foreground pt-1 border-t">
                  <Info className="h-4 w-4 shrink-0 text-muted-foreground" />
                  <span>
                    Each multi-agent research inquiry can execute up to {limits.tavily_searches_per_job_limit ?? 5} live web search queries.
                  </span>
                </div>
              </CardContent>
            </Card>
          </div>

          {/* Section 3: Usage History Table */}
          <Card className="shadow-sm">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg">Recent Usage Audit Log</CardTitle>
                  <CardDescription className="text-xs">
                    Granular, idempotent execution events linked to your research tasks
                  </CardDescription>
                </div>
                <span className="text-xs text-muted-foreground">
                  Showing {history.length} of {historyTotal} events
                </span>
              </div>
            </CardHeader>
            <CardContent>
              {history.length === 0 ? (
                <div className="py-12 text-center text-muted-foreground text-sm">
                  No usage events recorded yet. Initiate your first research job to view live telemetry.
                </div>
              ) : (
                <div className="overflow-x-auto">
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Timestamp</TableHead>
                        <TableHead>Provider</TableHead>
                        <TableHead>Operation</TableHead>
                        <TableHead>Model / Target</TableHead>
                        <TableHead className="text-right">Prompt</TableHead>
                        <TableHead className="text-right">Output</TableHead>
                        <TableHead className="text-right">Total Tokens</TableHead>
                        <TableHead>Type</TableHead>
                        <TableHead>Associated Job</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {history.map((event) => (
                        <TableRow key={event.id}>
                          <TableCell className="font-mono text-xs whitespace-nowrap">
                            {formatDate(event.created_at)}
                          </TableCell>
                          <TableCell>
                            <Badge
                              variant="outline"
                              className={`text-[10px] font-semibold ${
                                event.provider === "gemini"
                                  ? "border-primary/40 text-primary"
                                  : "border-blue-500/40 text-blue-500"
                              }`}
                            >
                              {event.provider}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-xs capitalize font-medium">
                            {event.operation_type.replace("_", " ")}
                          </TableCell>
                          <TableCell className="font-mono text-xs text-muted-foreground truncate max-w-[140px]" title={event.model_name || "-"}>
                            {event.model_name || (event.search_depth ? `depth: ${event.search_depth}` : "-")}
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs">
                            {event.input_tokens > 0 ? event.input_tokens.toLocaleString() : "-"}
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs">
                            {event.output_tokens > 0 ? event.output_tokens.toLocaleString() : "-"}
                          </TableCell>
                          <TableCell className="text-right font-mono text-xs font-semibold">
                            {event.total_tokens > 0
                              ? event.total_tokens.toLocaleString()
                              : event.embedding_tokens > 0
                              ? `${event.embedding_tokens.toLocaleString()} (emb)`
                              : event.request_count > 0
                              ? `${event.request_count} search`
                              : "-"}
                          </TableCell>
                          <TableCell>
                            {event.is_estimated ? (
                              <Badge variant="outline" className="text-[9px] py-0 px-1 text-muted-foreground">
                                Simulated
                              </Badge>
                            ) : (
                              <Badge variant="success" className="text-[9px] py-0 px-1">
                                Actual
                              </Badge>
                            )}
                          </TableCell>
                          <TableCell>
                            {event.job_id ? (
                              <Link
                                to={`/research/${event.job_id}`}
                                className="font-mono text-xs text-primary hover:underline"
                                title={event.job_id}
                              >
                                {event.job_id.substring(0, 8)}...
                              </Link>
                            ) : (
                              <span className="text-xs text-muted-foreground">Direct / RAG</span>
                            )}
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                </div>
              )}

              {/* Pagination controls */}
              {historyTotal > 15 && (
                <div className="flex items-center justify-between pt-4 border-t mt-4">
                  <span className="text-xs text-muted-foreground">
                    Page {historyPage} of {Math.ceil(historyTotal / 15)}
                  </span>
                  <div className="flex items-center gap-2">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                      disabled={historyPage === 1}
                      className="gap-1 h-8 px-2 text-xs"
                    >
                      <ChevronLeft className="h-4 w-4" /> Previous
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => setHistoryPage((p) => p + 1)}
                      disabled={historyPage * 15 >= historyTotal}
                      className="gap-1 h-8 px-2 text-xs"
                    >
                      Next <ChevronRight className="h-4 w-4" />
                    </Button>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </>
      ) : (
        /* Platform Admin Overview Tab */
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
            <Card className="shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground">Total Users</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{adminSummary?.total_users ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">Platform-registered accounts</p>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground">Total Research Jobs</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold">{adminSummary?.total_jobs ?? 0}</div>
                <p className="text-xs text-muted-foreground mt-1">
                  {adminSummary?.jobs_by_status?.completed || 0} completed, {adminSummary?.jobs_by_status?.failed || 0} failed
                </p>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground">Platform Tokens Consumed</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-primary">
                  {formatTokens(adminSummary?.gemini_total_tokens)}
                </div>
                <p className="text-xs text-muted-foreground mt-1">
                  {formatTokens(adminSummary?.gemini_input_tokens)} in / {formatTokens(adminSummary?.gemini_output_tokens)} out
                </p>
              </CardContent>
            </Card>

            <Card className="shadow-sm">
              <CardHeader className="pb-2">
                <CardTitle className="text-xs text-muted-foreground">Platform Web Searches</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-3xl font-bold text-blue-500">
                  {(adminSummary?.tavily_total_searches ?? 0).toLocaleString()}
                </div>
                <p className="text-xs text-muted-foreground mt-1">Total Tavily external calls</p>
              </CardContent>
            </Card>
          </div>

          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg">Per-User Platform Telemetry</CardTitle>
              <CardDescription className="text-xs">
                Administrative oversight of active accounts and resource consumption
              </CardDescription>
            </CardHeader>
            <CardContent>
              <div className="overflow-x-auto">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>User Email</TableHead>
                      <TableHead>Tier</TableHead>
                      <TableHead>Role</TableHead>
                      <TableHead className="text-right">Jobs Today</TableHead>
                      <TableHead className="text-right">Jobs Month</TableHead>
                      <TableHead className="text-right">Total Jobs</TableHead>
                      <TableHead className="text-right">Tokens Used</TableHead>
                      <TableHead className="text-right">Searches</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {adminUsers.map((u) => (
                      <TableRow key={u.user_id}>
                        <TableCell className="font-medium text-xs">{u.email}</TableCell>
                        <TableCell>
                          <Badge variant="outline" className="capitalize text-[10px]">
                            {u.tier}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-xs">{u.role}</TableCell>
                        <TableCell className="text-right font-mono text-xs">{u.jobs_today}</TableCell>
                        <TableCell className="text-right font-mono text-xs">{u.jobs_this_month}</TableCell>
                        <TableCell className="text-right font-mono text-xs font-semibold">{u.total_jobs}</TableCell>
                        <TableCell className="text-right font-mono text-xs text-primary font-semibold">
                          {formatTokens(u.total_tokens)}
                        </TableCell>
                        <TableCell className="text-right font-mono text-xs">{u.total_searches}</TableCell>
                        <TableCell>
                          {u.is_active ? (
                            <Badge variant="success" className="text-[10px]">Active</Badge>
                          ) : (
                            <Badge variant="destructive" className="text-[10px]">Deactivated</Badge>
                          )}
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        </div>
      )}
    </div>
  );
}

