import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Compass, FileText, Layers, PlusCircle, Sparkles, Cpu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { systemApi } from "@/services/api";

export function Navbar() {
  const location = useLocation();
  const [systemStatus, setSystemStatus] = useState(null);

  useEffect(() => {
    systemApi.getStatus()
      .then((data) => setSystemStatus(data))
      .catch((err) => console.error("Failed to fetch system status", err));
  }, []);

  const navItems = [
    { name: "Dashboard", path: "/", icon: Layers },
    { name: "Knowledge Base", path: "/knowledge-base", icon: FileText },
  ];

  const isLive = systemStatus?.effective_mode === "live";

  return (
    <header className="sticky top-0 z-40 w-full border-b bg-card/80 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="container flex h-16 items-center justify-between px-6 max-w-7xl">
        <div className="flex items-center gap-6">
          <Link to="/" className="flex items-center gap-2 font-bold text-xl tracking-tight text-primary">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-primary text-primary-foreground shadow-sm">
              <Compass className="h-5 w-5" />
            </div>
            <span>ResearchPilot</span>
          </Link>
          <nav className="flex items-center gap-1 sm:gap-2">
            {navItems.map((item) => {
              const Icon = item.icon;
              const isActive = location.pathname === item.path;
              return (
                <Link
                  key={item.path}
                  to={item.path}
                  className={`flex items-center gap-2 rounded-md px-3 py-2 text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-secondary text-primary font-semibold"
                      : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                  }`}
                >
                  <Icon className="h-4 w-4" />
                  <span>{item.name}</span>
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="flex items-center gap-4">
          {systemStatus && (
            <div
              className="hidden sm:flex items-center"
              title={`LLM: ${systemStatus.llm_provider.name} (${systemStatus.llm_provider.model}) | Search: ${systemStatus.web_search_provider.name}`}
            >
              {isLive ? (
                <Badge variant="success" className="gap-1.5 py-1 px-2.5 shadow-sm font-medium">
                  <Sparkles className="h-3.5 w-3.5" />
                  Live AI Mode
                </Badge>
              ) : (
                <Badge variant="warning" className="gap-1.5 py-1 px-2.5 shadow-sm font-medium">
                  <Cpu className="h-3.5 w-3.5" />
                  Mock Mode (Simulated AI)
                </Badge>
              )}
            </div>
          )}
          <Link to="/research/new">
            <Button size="sm" className="gap-2 shadow-sm">
              <PlusCircle className="h-4 w-4" />
              New Research
            </Button>
          </Link>
        </div>
      </div>
    </header>
  );
}
