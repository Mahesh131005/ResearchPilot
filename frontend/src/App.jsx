import React from "react";
import { BrowserRouter, Routes, Route, Navigate } from "react-router-dom";
import { AuthProvider } from "@/context/AuthContext";
import { ProtectedRoute } from "@/components/ProtectedRoute";
import { Navbar } from "@/components/Navbar";
import { Login } from "@/pages/Login";
import { Dashboard } from "@/pages/Dashboard";
import { KnowledgeBase } from "@/pages/KnowledgeBase";
import { NewResearch } from "@/pages/NewResearch";
import { ResearchExecution } from "@/pages/ResearchExecution";
import { ReportViewer } from "@/pages/ReportViewer";
import { Usage } from "@/pages/Usage";
import { Billing } from "@/pages/Billing";

export default function App() {
  return (
    <BrowserRouter>
      <AuthProvider>
        <div className="min-h-screen flex flex-col bg-background text-foreground antialiased selection:bg-primary/20">
          <Navbar />
          <main className="flex-1">
            <Routes>
              {/* Public Authentication Route */}
              <Route path="/login" element={<Login />} />

              {/* Protected Platform Routes */}
              <Route
                path="/"
                element={
                  <ProtectedRoute>
                    <Dashboard />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/usage"
                element={
                  <ProtectedRoute>
                    <Usage />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/billing"
                element={
                  <ProtectedRoute>
                    <Billing />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/knowledge-base"
                element={
                  <ProtectedRoute>
                    <KnowledgeBase />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/research/new"
                element={
                  <ProtectedRoute>
                    <NewResearch />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/research/:jobId"
                element={
                  <ProtectedRoute>
                    <ResearchExecution />
                  </ProtectedRoute>
                }
              />
              <Route
                path="/research/:jobId/report"
                element={
                  <ProtectedRoute>
                    <ReportViewer />
                  </ProtectedRoute>
                }
              />

              {/* Fallback */}
              <Route path="*" element={<Navigate to="/" replace />} />
            </Routes>
          </main>
        </div>
      </AuthProvider>
    </BrowserRouter>
  );
}
