import React, { useState, useEffect, useRef } from "react";
import { documentApi, qaApi } from "@/services/api";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Input } from "@/components/ui/input";
import { Tabs, TabsList, TabsTrigger, TabsContent } from "@/components/ui/tabs";
import {
  Table,
  TableHeader,
  TableBody,
  TableRow,
  TableHead,
  TableCell,
} from "@/components/ui/table";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import {
  FileText,
  UploadCloud,
  Trash2,
  Eye,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Layers,
  FileCheck,
  Search,
  Sparkles,
  BookmarkCheck,
  HelpCircle,
} from "lucide-react";

export function KnowledgeBase() {
  const [documents, setDocuments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [uploadError, setUploadError] = useState(null);
  
  // Chunk inspection modal state
  const [selectedDoc, setSelectedDoc] = useState(null);
  const [docChunks, setDocChunks] = useState([]);
  const [loadingChunks, setLoadingChunks] = useState(false);
  const [chunkModalOpen, setChunkModalOpen] = useState(false);
  
  // Q&A State
  const [qaQuery, setQaQuery] = useState("");
  const [selectedQaDoc, setSelectedQaDoc] = useState("");
  const [qaLoading, setQaLoading] = useState(false);
  const [qaResult, setQaResult] = useState(null);
  const [qaError, setQaError] = useState(null);

  const fileInputRef = useRef(null);

  useEffect(() => {
    loadDocuments();
    const interval = setInterval(() => {
      setDocuments((prev) => {
        const hasProcessing = prev.some((d) => d.status === "processing" || d.status === "pending");
        if (hasProcessing) {
          loadDocuments(false);
        }
        return prev;
      });
    }, 3000);
    return () => clearInterval(interval);
  }, []);

  const loadDocuments = async (showLoading = true) => {
    if (showLoading) setLoading(true);
    try {
      const data = await documentApi.list();
      setDocuments(data || []);
    } catch (err) {
      console.error("Failed to load documents", err);
    } finally {
      if (showLoading) setLoading(false);
    }
  };

  const handleFileSelect = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;

    if (!file.name.toLowerCase().endsWith(".pdf")) {
      setUploadError("Only valid PDF documents (.pdf) are accepted.");
      return;
    }
    if (file.size > 25 * 1024 * 1024) {
      setUploadError("File exceeds maximum allowed size of 25MB.");
      return;
    }

    try {
      setUploadError(null);
      setUploading(true);
      await documentApi.upload(file);
      await loadDocuments(false);
    } catch (err) {
      console.error("Upload failed", err);
      const msg = err.response?.data?.detail || "Upload failed. Please ensure the file is a valid PDF.";
      setUploadError(msg);
    } finally {
      setUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Are you sure you want to delete this document and its vector chunks?")) {
      return;
    }
    try {
      await documentApi.delete(id);
      setDocuments((prev) => prev.filter((d) => d.id !== id));
      if (selectedQaDoc === id) setSelectedQaDoc("");
    } catch (err) {
      alert("Failed to delete document: " + (err.response?.data?.detail || err.message));
    }
  };

  const handleInspectChunks = async (doc) => {
    setSelectedDoc(doc);
    setChunkModalOpen(true);
    setLoadingChunks(true);
    try {
      const chunks = await documentApi.getChunks(doc.id);
      setDocChunks(chunks || []);
    } catch (err) {
      console.error("Failed to load chunks", err);
      setDocChunks([]);
    } finally {
      setLoadingChunks(false);
    }
  };

  const handleRunQA = async (e) => {
    e.preventDefault();
    if (!qaQuery.trim()) return;

    try {
      setQaLoading(true);
      setQaError(null);
      setQaResult(null);
      const res = await qaApi.query(
        qaQuery,
        selectedQaDoc ? selectedQaDoc : null,
        5
      );
      setQaResult(res);
    } catch (err) {
      console.error("QA Query failed", err);
      setQaError(err.response?.data?.detail || "Failed to execute semantic query.");
    } finally {
      setQaLoading(false);
    }
  };

  return (
    <div className="container py-8 space-y-8 px-6 max-w-7xl">
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <div>
          <h1 className="text-3xl font-bold tracking-tight">Knowledge Base</h1>
          <p className="text-muted-foreground mt-1">
            Manage your research PDFs and perform grounded semantic search with page-level citations.
          </p>
        </div>
        <div className="flex items-center gap-3">
          <Button
            variant="outline"
            size="sm"
            onClick={() => loadDocuments(true)}
            disabled={loading}
            className="gap-2"
          >
            <RefreshCw className={`h-4 w-4 ${loading ? "animate-spin" : ""}`} />
            Refresh
          </Button>
          <input
            type="file"
            ref={fileInputRef}
            onChange={handleFileSelect}
            accept=".pdf,application/pdf"
            className="hidden"
          />
          <Button
            onClick={() => fileInputRef.current?.click()}
            disabled={uploading}
            className="gap-2"
          >
            <UploadCloud className="h-4 w-4" />
            {uploading ? "Ingesting & Embedding..." : "Upload PDF"}
          </Button>
        </div>
      </div>

      {uploadError && (
        <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-center justify-between">
          <div className="flex items-center gap-2">
            <AlertCircle className="h-4 w-4 flex-shrink-0" />
            <span>{uploadError}</span>
          </div>
          <button
            onClick={() => setUploadError(null)}
            className="text-xs font-semibold hover:underline"
          >
            Dismiss
          </button>
        </div>
      )}

      <Tabs defaultValue="documents" className="w-full">
        <TabsList className="grid w-full max-w-md grid-cols-2">
          <TabsTrigger value="documents" className="gap-2">
            <FileText className="h-4 w-4" />
            Documents ({documents.length})
          </TabsTrigger>
          <TabsTrigger value="qa" className="gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            Ask Documents (RAG)
          </TabsTrigger>
        </TabsList>

        {/* Tab 1: Documents Management */}
        <TabsContent value="documents" className="space-y-6 mt-6">
          {/* Drag & Drop Upload Banner */}
          <div
            onClick={() => fileInputRef.current?.click()}
            className="border-2 border-dashed rounded-xl p-8 text-center hover:border-primary/50 hover:bg-muted/30 transition cursor-pointer flex flex-col items-center justify-center space-y-3"
          >
            <div className="h-12 w-12 rounded-full bg-primary/10 text-primary flex items-center justify-center">
              <UploadCloud className="h-6 w-6" />
            </div>
            <div>
              <p className="text-sm font-semibold text-foreground">
                Click to upload or drag and drop PDF research papers
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Parsed via PyMuPDF • Automatically token-chunked & embedded into pgvector
              </p>
            </div>
            {uploading && (
              <div className="w-full max-w-xs space-y-2 pt-2">
                <Progress value={75} className="h-1.5" />
                <p className="text-xs text-muted-foreground">Extracting text & generating vector embeddings...</p>
              </div>
            )}
          </div>

          <Card className="shadow-sm border">
            <CardHeader>
              <CardTitle>Uploaded Documents</CardTitle>
              <CardDescription>
                All documents indexed with vector embeddings for semantic retrieval.
              </CardDescription>
            </CardHeader>
            <CardContent>
              {loading ? (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  Loading documents...
                </div>
              ) : documents.length === 0 ? (
                <div className="py-12 text-center text-sm text-muted-foreground">
                  No documents in knowledge base. Upload a PDF above to begin.
                </div>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Filename</TableHead>
                      <TableHead>Pages</TableHead>
                      <TableHead>Chunks</TableHead>
                      <TableHead>File Size</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Uploaded</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {documents.map((doc) => (
                      <TableRow key={doc.id}>
                        <TableCell className="font-medium">
                          <div className="flex items-center gap-2">
                            <FileText className="h-4 w-4 text-primary flex-shrink-0" />
                            <span className="truncate max-w-xs">{doc.filename}</span>
                          </div>
                        </TableCell>
                        <TableCell>{doc.page_count ?? "—"}</TableCell>
                        <TableCell>
                          <span className="inline-flex items-center gap-1">
                            <Layers className="h-3.5 w-3.5 text-muted-foreground" />
                            {doc.total_chunks ?? 0}
                          </span>
                        </TableCell>
                        <TableCell>
                          {(doc.file_size / (1024 * 1024)).toFixed(2)} MB
                        </TableCell>
                        <TableCell>
                          {doc.status === "completed" && (
                            <Badge variant="success" className="capitalize">
                              Indexed
                            </Badge>
                          )}
                          {doc.status === "processing" && (
                            <Badge variant="warning" className="capitalize animate-pulse">
                              Processing
                            </Badge>
                          )}
                          {doc.status === "failed" && (
                            <Badge variant="destructive" className="capitalize">
                              Failed
                            </Badge>
                          )}
                        </TableCell>
                        <TableCell className="text-xs text-muted-foreground">
                          {new Date(doc.created_at).toLocaleDateString()}
                        </TableCell>
                        <TableCell className="text-right">
                          <div className="flex items-center justify-end gap-2">
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleInspectChunks(doc)}
                              title="Inspect Chunks"
                            >
                              <Eye className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="ghost"
                              size="icon"
                              onClick={() => handleDelete(doc.id)}
                              title="Delete Document"
                              className="text-destructive hover:text-destructive hover:bg-destructive/10"
                            >
                              <Trash2 className="h-4 w-4" />
                            </Button>
                          </div>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* Tab 2: Document Q&A & Semantic Search */}
        <TabsContent value="qa" className="space-y-6 mt-6">
          <Card className="shadow-sm border">
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Sparkles className="h-5 w-5 text-primary" />
                Semantic Document Query & Citation Harness
              </CardTitle>
              <CardDescription>
                Ask questions against your uploaded research PDFs. Answers are strictly grounded in retrieved vector chunks with exact page-level citations.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-6">
              <form onSubmit={handleRunQA} className="space-y-4">
                <div className="grid gap-4 sm:grid-cols-3">
                  <div className="sm:col-span-2">
                    <label className="text-xs font-semibold text-muted-foreground mb-1 block">
                      Research Question
                    </label>
                    <Input
                      placeholder="e.g. What are the Reserve Bank of India's guidelines on AI governance?"
                      value={qaQuery}
                      onChange={(e) => setQaQuery(e.target.value)}
                      disabled={qaLoading}
                    />
                  </div>
                  <div>
                    <label className="text-xs font-semibold text-muted-foreground mb-1 block">
                      Target Document (Optional)
                    </label>
                    <select
                      className="flex h-10 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background"
                      value={selectedQaDoc}
                      onChange={(e) => setSelectedQaDoc(e.target.value)}
                      disabled={qaLoading}
                    >
                      <option value="">All Documents in Knowledge Base</option>
                      {documents.map((d) => (
                        <option key={d.id} value={d.id}>
                          {d.filename}
                        </option>
                      ))}
                    </select>
                  </div>
                </div>

                <div className="flex justify-end">
                  <Button type="submit" disabled={qaLoading || !qaQuery.trim()} className="gap-2">
                    <Search className={`h-4 w-4 ${qaLoading ? "animate-spin" : ""}`} />
                    {qaLoading ? "Retrieving & Synthesizing..." : "Query Knowledge Base"}
                  </Button>
                </div>
              </form>

              {qaError && (
                <div className="rounded-lg border border-destructive/20 bg-destructive/10 p-4 text-sm text-destructive flex items-center gap-2">
                  <AlertCircle className="h-4 w-4 flex-shrink-0" />
                  <span>{qaError}</span>
                </div>
              )}

              {/* QA Results Section */}
              {qaResult && (
                <div className="space-y-6 pt-4 border-t">
                  <div className="rounded-xl border bg-card p-6 space-y-4 shadow-sm">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BookmarkCheck className="h-5 w-5 text-primary" />
                        <h4 className="font-semibold text-base text-foreground">
                          Synthesized Answer
                        </h4>
                      </div>
                      <div>
                        {qaResult.has_sufficient_evidence ? (
                          <Badge variant="success">Evidence Grounded</Badge>
                        ) : (
                          <Badge variant="warning">Insufficient Evidence</Badge>
                        )}
                      </div>
                    </div>

                    <p className="text-sm leading-relaxed text-foreground whitespace-pre-wrap">
                      {qaResult.answer}
                    </p>

                    {/* Citations List */}
                    {qaResult.citations && qaResult.citations.length > 0 && (
                      <div className="pt-3 border-t">
                        <p className="text-xs font-semibold text-muted-foreground mb-2">
                          Page-Level Citations:
                        </p>
                        <div className="flex flex-wrap gap-2">
                          {qaResult.citations.map((c, idx) => (
                            <span
                              key={idx}
                              className="inline-flex items-center gap-1.5 rounded-md bg-primary/10 px-2.5 py-1 text-xs font-medium text-primary border border-primary/20"
                            >
                              <FileText className="h-3.5 w-3.5" />
                              {c.filename} — Page {c.page_number}
                            </span>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>

                  {/* Retrieved Evidence Chunks */}
                  <div className="space-y-3">
                    <h4 className="font-semibold text-sm text-foreground flex items-center gap-2">
                      <Layers className="h-4 w-4 text-muted-foreground" />
                      Retrieved Vector Chunks ({qaResult.evidence?.length || 0})
                    </h4>
                    <div className="grid gap-3 sm:grid-cols-2">
                      {qaResult.evidence?.map((ev, idx) => (
                        <div
                          key={ev.chunk_id || idx}
                          className="rounded-lg border bg-muted/20 p-4 text-xs space-y-2 flex flex-col justify-between"
                        >
                          <div>
                            <div className="flex items-center justify-between text-muted-foreground font-semibold mb-1">
                              <span className="truncate max-w-[180px]">{ev.filename}</span>
                              <Badge variant="outline" className="text-[10px]">
                                Page {ev.page_number}
                              </Badge>
                            </div>
                            <p className="text-foreground font-mono leading-relaxed bg-background/60 p-2.5 rounded border line-clamp-4">
                              {ev.content}
                            </p>
                          </div>
                          <div className="flex items-center justify-between text-muted-foreground pt-1 border-t text-[11px]">
                            <span>Chunk #{ev.chunk_index + 1}</span>
                            <span className="font-semibold text-primary">
                              Similarity: {(ev.similarity_score * 100).toFixed(1)}%
                            </span>
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      {/* Chunk Inspection Dialog */}
      <Dialog open={chunkModalOpen} onOpenChange={setChunkModalOpen}>
        <DialogContent className="max-w-2xl max-h-[80vh] flex flex-col">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2">
              <FileCheck className="h-5 w-5 text-primary" />
              Document Chunks & Provenance
            </DialogTitle>
            <DialogDescription>
              {selectedDoc?.filename} • Total chunks: {docChunks.length}
            </DialogDescription>
          </DialogHeader>

          <div className="flex-1 overflow-y-auto space-y-3 pr-2 py-4">
            {loadingChunks ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                Loading chunk provenance details...
              </div>
            ) : docChunks.length === 0 ? (
              <div className="py-8 text-center text-sm text-muted-foreground">
                No chunks found for this document.
              </div>
            ) : (
              docChunks.map((chunk, idx) => (
                <div
                  key={chunk.id || idx}
                  className="rounded-lg border bg-muted/30 p-3 text-xs space-y-1.5"
                >
                  <div className="flex items-center justify-between text-muted-foreground font-semibold">
                    <span>Chunk #{chunk.chunk_index + 1}</span>
                    <Badge variant="outline" className="text-[10px]">
                      Page {chunk.page_number}
                    </Badge>
                  </div>
                  <p className="text-foreground font-mono leading-relaxed bg-background/50 p-2 rounded border">
                    {chunk.content}
                  </p>
                  <div className="text-[11px] text-muted-foreground flex items-center justify-between">
                    <span>Token count: ~{chunk.token_count || "—"}</span>
                    <span>ID: {chunk.id}</span>
                  </div>
                </div>
              ))
            )}
          </div>
        </DialogContent>
      </Dialog>
    </div>
  );
}
