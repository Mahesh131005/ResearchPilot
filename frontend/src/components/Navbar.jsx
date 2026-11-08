import React, { useState, useEffect } from "react";
import { Link, useLocation } from "react-router-dom";
import { Compass, FileText, Layers, PlusCircle, Sparkles, Cpu, LogOut, User, Shield, Gauge, CreditCard } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { systemApi } from "@/services/api";
import { useAuth } from "@/context/AuthContext";

export function Navbar() {
  const location = useLocation();
  const [systemStatus, setSystemStatus] = useState(null);
  const { user, logout } = useAuth();

  useEffect(() => {
    systemApi.getStatus()
      .then((data) => setSystemStatus(data))
      .catch((err) => console.error("Failed to fetch system status", err));
  }, []);

  const navItems = [
    { name: "Dashboard", path: "/", icon: Layers },
    { name: "Knowledge Base", path: "/knowledge-base", icon: FileText },
    { name: "Usage & Quotas", path: "/usage", icon: Gauge },
    { name: "Billing", path: "/billing", icon: CreditCard },
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
        <div className="flex items-center gap-3">
          {systemStatus && (
            <div
              className="hidden md:flex items-center"
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
                  Mock Mode
                </Badge>
              )}
            </div>
          )}

          <Link to="/research/new">
            <Button size="sm" className="gap-2 shadow-sm">
              <PlusCircle className="h-4 w-4" />
              <span className="hidden sm:inline">New Research</span>
            </Button>
          </Link>

          {user ? (
            <div className="flex items-center gap-2 pl-2 border-l border-border">
              <div className="hidden lg:flex flex-col text-right">
                <span className="text-xs font-semibold text-foreground truncate max-w-[140px]" title={user.email}>
                  {user.email}
                </span>
                <span className="text-[10px] text-muted-foreground capitalize flex items-center justify-end gap-1">
                  {user.role === "admin" && <Shield className="h-2.5 w-2.5 text-primary" />}
                  {user.role} ({user.tier})
                </span>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={logout}
                title="Sign out of ResearchPilot"
                className="gap-1.5 h-8 px-2.5 text-xs text-muted-foreground hover:text-foreground"
              >
                <LogOut className="h-3.5 w-3.5" />
                <span className="hidden sm:inline">Sign Out</span>
              </Button>
            </div>
          ) : (
            <Link to="/login">
              <Button variant="outline" size="sm" className="gap-1.5 h-8">
                <User className="h-3.5 w-3.5" />
                Sign In
              </Button>
            </Link>
          )}
        </div>
      </div>
    </header>
  );
}
