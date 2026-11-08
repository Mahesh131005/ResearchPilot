import React, { useState } from "react";
import { Navigate, useLocation } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Card, CardHeader, CardTitle, CardDescription, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ShieldAlert, KeyRound, CheckCircle2 } from "lucide-react";

export function ProtectedRoute({ children }) {
  const { user, accessToken, isLoading, mustChangePassword, changePassword } = useAuth();
  const location = useLocation();

  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState(null);
  const [isSubmitting, setIsSubmitting] = useState(false);

  if (isLoading) {
    return (
      <div className="min-h-[60vh] flex flex-col items-center justify-center gap-3">
        <div className="h-8 w-8 animate-spin rounded-full border-4 border-primary border-t-transparent" />
        <p className="text-sm text-muted-foreground animate-pulse">Authenticating session...</p>
      </div>
    );
  }

  if (!accessToken || !user) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (mustChangePassword) {
    const handlePasswordChange = async (e) => {
      e.preventDefault();
      setError(null);

      if (newPassword !== confirmPassword) {
        setError("New passwords do not match.");
        return;
      }

      if (newPassword.length < 10) {
        setError("New password must be at least 10 characters long.");
        return;
      }

      setIsSubmitting(true);
      try {
        await changePassword(currentPassword, newPassword);
      } catch (err) {
        setError(err.response?.data?.detail || "Failed to update password. Check your current password.");
      } finally {
        setIsSubmitting(false);
      }
    };

    return (
      <div className="min-h-[70vh] flex items-center justify-center p-4">
        <Card className="w-full max-w-md border-amber-500/30 shadow-lg">
          <CardHeader className="text-center pb-2">
            <div className="mx-auto mb-3 flex h-12 w-12 items-center justify-center rounded-full bg-amber-500/10 text-amber-500">
              <ShieldAlert className="h-6 w-6" />
            </div>
            <CardTitle className="text-xl">Password Change Required</CardTitle>
            <CardDescription>
              Security policy requires changing your password upon first sign-in before accessing research features.
            </CardDescription>
          </CardHeader>
          <form onSubmit={handlePasswordChange}>
            <CardContent className="space-y-4 pt-2">
              {error && (
                <div className="rounded-md bg-destructive/10 border border-destructive/20 p-3 text-xs text-destructive">
                  {error}
                </div>
              )}
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">Current Password</label>
                <input
                  type="password"
                  required
                  value={currentPassword}
                  onChange={(e) => setCurrentPassword(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="Enter current password"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">New Password</label>
                <input
                  type="password"
                  required
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="At least 10 chars (A-Z, a-z, 0-9, symbol)"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-semibold text-foreground">Confirm New Password</label>
                <input
                  type="password"
                  required
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary"
                  placeholder="Confirm new password"
                />
              </div>
              <div className="rounded-md bg-secondary/50 p-2.5 text-[11px] text-muted-foreground space-y-1">
                <div className="font-semibold text-foreground flex items-center gap-1">
                  <KeyRound className="h-3.5 w-3.5 text-primary" /> Complexity Requirements:
                </div>
                <div>• Minimum 10 characters</div>
                <div>• Uppercase (A-Z), lowercase (a-z), number (0-9), and special symbol (!@#$...)</div>
              </div>
            </CardContent>
            <CardFooter>
              <Button type="submit" className="w-full" disabled={isSubmitting}>
                {isSubmitting ? "Updating Password..." : "Set New Password & Continue"}
              </Button>
            </CardFooter>
          </form>
        </Card>
      </div>
    );
  }

  return children;
}

