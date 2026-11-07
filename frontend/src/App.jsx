import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { Navbar } from "@/components/Navbar";
import { Dashboard } from "@/pages/Dashboard";
import { KnowledgeBase } from "@/pages/KnowledgeBase";
import { NewResearch } from "@/pages/NewResearch";
import { ResearchExecution } from "@/pages/ResearchExecution";
import { ReportViewer } from "@/pages/ReportViewer";

export default function App() {
  return (
    <BrowserRouter>
      <div className="min-h-screen flex flex-col bg-background text-foreground antialiased selection:bg-primary/20">
        <Navbar />
        <main className="flex-1">
          <Routes>
            <Route path="/" element={<Dashboard />} />
            <Route path="/knowledge-base" element={<KnowledgeBase />} />
            <Route path="/research/new" element={<NewResearch />} />
            <Route path="/research/:jobId" element={<ResearchExecution />} />
            <Route path="/research/:jobId/report" element={<ReportViewer />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  );
}
