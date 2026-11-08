import React, { useState } from "react";
import { useNavigate, useLocation, Link } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Compass, Lock, Mail, ShieldCheck, ArrowRight, UserPlus, LogIn } from "lucide-react";

export function Login() {
  const [isRegister, setIsRegister] = useState(false);
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [loading, setLoading] = useState(false);

  const { login, register } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();

  const from = location.state?.from?.pathname || "/";

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(null);

    if (isRegister) {
      if (password !== confirmPassword) {
        setError("Passwords do not match.");
        return;
      }
      if (password.length < 10) {
        setError("Password must be at least 10 characters long.");
        return;
      }
    }

    setLoading(true);
    try {
      if (isRegister) {
        await register(email, password);
      } else {
        await login(email, password);
      }
      navigate(from, { replace: true });
    } catch (err) {
      const msg = err.response?.data?.detail || "Authentication failed. Please verify your credentials.";
      setError(msg);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-[80vh] flex items-center justify-center p-4">
      <Card className="w-full max-w-md border-border/80 shadow-xl bg-card">
        <CardHeader className="text-center space-y-2 pb-4">
          <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-xl bg-primary text-primary-foreground shadow-md">
            <Compass className="h-6 w-6" />
          </div>
          <CardTitle className="text-2xl font-bold tracking-tight">
            {isRegister ? "Create ResearchPilot Account" : "Sign in to ResearchPilot"}
          </CardTitle>
          <CardDescription className="text-sm">
            {isRegister
              ? "Join the multi-agent AI research platform with verified citations"
              : "Access your research history, documents, and synthesis reports"}
          </CardDescription>
        </CardHeader>

        {/* Tab switcher */}
        <div className="flex border-b border-border px-6">
          <button
            type="button"
            onClick={() => {
              setIsRegister(false);
              setError(null);
            }}
            className={`flex-1 pb-2.5 text-sm font-semibold border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
              !isRegister
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <LogIn className="h-4 w-4" /> Sign In
          </button>
          <button
            type="button"
            onClick={() => {
              setIsRegister(true);
              setError(null);
            }}
            className={`flex-1 pb-2.5 text-sm font-semibold border-b-2 transition-colors flex items-center justify-center gap-1.5 ${
              isRegister
                ? "border-primary text-primary"
                : "border-transparent text-muted-foreground hover:text-foreground"
            }`}
          >
            <UserPlus className="h-4 w-4" /> Register
          </button>
        </div>

        <form onSubmit={handleSubmit}>
          <CardContent className="space-y-4 pt-6">
            {error && (
              <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-xs text-destructive">
                {error}
              </div>
            )}

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Mail className="h-3.5 w-3.5 text-muted-foreground" /> Email Address
              </label>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="name@example.com"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            <div className="space-y-1.5">
              <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                <Lock className="h-3.5 w-3.5 text-muted-foreground" /> Password
              </label>
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                placeholder="••••••••••••"
                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>

            {isRegister && (
              <>
                <div className="space-y-1.5">
                  <label className="text-xs font-semibold text-foreground flex items-center gap-1.5">
                    <ShieldCheck className="h-3.5 w-3.5 text-muted-foreground" /> Confirm Password
                  </label>
                  <input
                    type="password"
                    required
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    placeholder="••••••••••••"
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  />
                </div>

                <div className="rounded-md bg-secondary/50 p-2.5 text-[11px] text-muted-foreground space-y-1">
                  <div className="font-semibold text-foreground">Password Policy:</div>
                  <div>• Minimum 10 characters</div>
                  <div>• Requires uppercase, lowercase, number, and special character</div>
                </div>
              </>
            )}
          </CardContent>

          <CardFooter className="flex flex-col gap-3">
            <Button type="submit" className="w-full gap-2" disabled={loading}>
              {loading ? (
                "Authenticating..."
              ) : isRegister ? (
                <>
                  Create Account <ArrowRight className="h-4 w-4" />
                </>
              ) : (
                <>
                  Sign In <ArrowRight className="h-4 w-4" />
                </>
              )}
            </Button>
          </CardFooter>
        </form>
      </Card>
    </div>
  );
}

