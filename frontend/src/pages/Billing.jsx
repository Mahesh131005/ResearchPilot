import React, { useState, useEffect } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  Wallet,
  CreditCard,
  DollarSign,
  TrendingUp,
  History,
  Shield,
  AlertCircle,
  CheckCircle2,
  RefreshCw,
  ExternalLink,
  Layers,
  Sparkles,
  Info,
  Clock,
  ArrowUpRight,
  ArrowDownLeft,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  Table,
  TableHeader,
  TableBody,
  TableHead,
  TableRow,
  TableCell,
} from "@/components/ui/table";
import { billingApi } from "@/services/api";
import { useAuth } from "@/context/AuthContext";

export function Billing() {
  const { user } = useAuth();
  const [searchParams] = useSearchParams();
  const [overview, setOverview] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [topupAmount, setTopupAmount] = useState(10);
  const [checkingOut, setCheckingOut] = useState(false);
  const [checkoutMsg, setCheckoutMsg] = useState(null);

  // Admin state
  const [adminOverview, setAdminOverview] = useState(null);
  const [activeTab, setActiveTab] = useState("wallet"); // "wallet", "pricing", "admin"

  const paymentStatus = searchParams.get("payment");

  const fetchBillingData = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await billingApi.getOverview();
      setOverview(data);

      if (user?.role === "admin") {
        try {
          const adm = await billingApi.getAdminOverview();
          setAdminOverview(adm);
        } catch (aErr) {
          console.warn("Failed to load admin billing metrics:", aErr);
        }
      }
    } catch (err) {
      console.error("Failed to load billing overview:", err);
      setError(err.response?.data?.detail || "Failed to load billing information.");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchBillingData();
  }, [user]);

  const handleTopup = async (amount) => {
    setCheckingOut(true);
    setCheckoutMsg(null);
    try {
      const session = await billingApi.createCheckout(amount);
      if (session.checkout_url) {
        if (session.mode === "mock") {
          setCheckoutMsg(`Simulated checkout created (${session.session_id}). Simulated payment credited.`);
          await fetchBillingData();
        } else {
          window.location.href = session.checkout_url;
        }
      }
    } catch (err) {
      console.error("Checkout initiation failed:", err);
      setError(err.response?.data?.detail || "Failed to create checkout session.");
    } finally {
      setCheckingOut(false);
    }
  };

  if (loading) {
    return (
      <div className="flex flex-col items-center justify-center min-h-[60vh] gap-3">
        <RefreshCw className="h-8 w-8 animate-spin text-primary" />
        <p className="text-muted-foreground text-sm">Loading billing ledger and wallet balance...</p>
      </div>
    );
  }

  const wallet = overview?.wallet;
  const transactions = overview?.recent_transactions || [];
  const pricing = overview?.pricing_matrix || [];

  return (
    <div className="space-y-8 max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8">
      {/* Top Header */}
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <div className="flex items-center gap-3">
            <h1 className="text-3xl font-bold tracking-tight">Billing & Monetization</h1>
            <Badge variant="outline" className="capitalize text-xs font-semibold px-2.5 py-0.5">
              {wallet?.tier || "Free"} Tier
            </Badge>
            {overview?.global_circuit_breaker_active && (
              <Badge variant="destructive" className="flex items-center gap-1 text-xs">
                <AlertCircle className="h-3 w-3" />
                Spending Paused
              </Badge>
            )}
          </div>
          <p className="text-muted-foreground mt-1 text-sm">
            Institutional cost accounting, atomic budget reservations, credit top-up, and provider pricing transparency.
          </p>
        </div>

        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" onClick={fetchBillingData} className="gap-2">
            <RefreshCw className="h-4 w-4" />
            Refresh
          </Button>
          <Link to="/usage">
            <Button variant="ghost" size="sm" className="gap-2">
              <Layers className="h-4 w-4" />
              Usage Quotas
            </Button>
          </Link>
        </div>
      </div>

      {paymentStatus === "success" && (
        <div className="p-4 rounded-lg bg-emerald-50 dark:bg-emerald-950/40 border border-emerald-200 dark:border-emerald-800 flex items-center gap-3 text-emerald-800 dark:text-emerald-300">
          <CheckCircle2 className="h-5 w-5 shrink-0" />
          <div>
            <p className="font-semibold text-sm">Payment Succeeded!</p>
            <p className="text-xs">Your credit balance has been replenished and credited to your wallet ledger.</p>
          </div>
        </div>
      )}

      {checkoutMsg && (
        <div className="p-4 rounded-lg bg-blue-50 dark:bg-blue-950/40 border border-blue-200 dark:border-blue-800 flex items-center gap-3 text-blue-800 dark:text-blue-300">
          <Info className="h-5 w-5 shrink-0" />
          <p className="text-sm">{checkoutMsg}</p>
        </div>
      )}

      {error && (
        <div className="p-4 rounded-lg bg-red-50 dark:bg-red-950/40 border border-red-200 dark:border-red-800 flex items-center gap-3 text-red-800 dark:text-red-300">
          <AlertCircle className="h-5 w-5 shrink-0" />
          <p className="text-sm">{error}</p>
        </div>
      )}

      {/* Navigation Tabs */}
      <div className="flex items-center gap-2 border-b border-border pb-2">
        <Button
          variant={activeTab === "wallet" ? "default" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("wallet")}
          className="gap-2"
        >
          <Wallet className="h-4 w-4" />
          Wallet & Transactions
        </Button>
        <Button
          variant={activeTab === "pricing" ? "default" : "ghost"}
          size="sm"
          onClick={() => setActiveTab("pricing")}
          className="gap-2"
        >
          <DollarSign className="h-4 w-4" />
          Provider Rates
        </Button>
        {user?.role === "admin" && (
          <Button
            variant={activeTab === "admin" ? "default" : "ghost"}
            size="sm"
            onClick={() => setActiveTab("admin")}
            className="gap-2 text-primary"
          >
            <Shield className="h-4 w-4" />
            Admin Financials
          </Button>
        )}
      </div>

      {activeTab === "wallet" && (
        <div className="space-y-8">
          {/* Metrics Overview Cards */}
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <Card className="border-l-4 border-l-emerald-500 shadow-sm">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs font-medium uppercase tracking-wider">
                  Available Balance
                </CardDescription>
                <CardTitle className="text-3xl font-bold flex items-baseline gap-1 text-emerald-600 dark:text-emerald-400">
                  ${wallet?.available_balance_usd?.toFixed(2) || "0.00"}
                  <span className="text-xs font-normal text-muted-foreground">USD</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                Total Balance: ${wallet?.balance_usd?.toFixed(4) || "0.0000"}
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-amber-500 shadow-sm">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs font-medium uppercase tracking-wider">
                  Reserved Holds
                </CardDescription>
                <CardTitle className="text-3xl font-bold flex items-baseline gap-1 text-amber-600 dark:text-amber-400">
                  ${wallet?.reserved_usd?.toFixed(2) || "0.00"}
                  <span className="text-xs font-normal text-muted-foreground">USD</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                In-flight holds ($0.05 / active job)
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-blue-500 shadow-sm">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs font-medium uppercase tracking-wider">
                  Lifetime Settled
                </CardDescription>
                <CardTitle className="text-3xl font-bold flex items-baseline gap-1 text-blue-600 dark:text-blue-400">
                  ${wallet?.lifetime_spent_usd?.toFixed(2) || "0.00"}
                  <span className="text-xs font-normal text-muted-foreground">USD</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                Cumulative completed research cost
              </CardContent>
            </Card>

            <Card className="border-l-4 border-l-purple-500 shadow-sm">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs font-medium uppercase tracking-wider">
                  Monthly Budget Limit
                </CardDescription>
                <CardTitle className="text-3xl font-bold flex items-baseline gap-1 text-purple-600 dark:text-purple-400">
                  ${wallet?.monthly_budget_usd?.toFixed(2) || "25.00"}
                  <span className="text-xs font-normal text-muted-foreground">USD</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="text-xs text-muted-foreground">
                Tier ceiling for current billing cycle
              </CardContent>
            </Card>
          </div>

          {/* Top-up Credits Section */}
          <Card className="shadow-sm">
            <CardHeader>
              <CardTitle className="text-lg flex items-center gap-2">
                <CreditCard className="h-5 w-5 text-primary" />
                Add Research Credits
              </CardTitle>
              <CardDescription>
                Prepay AI computation credits to run automated deep investigations without interruption.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                {[5, 10, 25, 50].map((amt) => (
                  <Button
                    key={amt}
                    type="button"
                    variant={topupAmount === amt ? "default" : "outline"}
                    className="h-16 flex flex-col items-center justify-center gap-1"
                    onClick={() => setTopupAmount(amt)}
                  >
                    <span className="text-lg font-bold">${amt}</span>
                    <span className="text-[10px] text-muted-foreground">
                      ~{amt * 20} standard investigations
                    </span>
                  </Button>
                ))}
              </div>

              <div className="flex flex-col sm:flex-row items-center justify-between pt-4 border-t border-border gap-4">
                <div className="text-xs text-muted-foreground flex items-center gap-2">
                  <Shield className="h-4 w-4 text-emerald-500" />
                  Payments processed securely via Stripe. Complimentary $1.00 starter balance credited on registration.
                </div>
                <Button
                  onClick={() => handleTopup(topupAmount)}
                  disabled={checkingOut}
                  className="w-full sm:w-auto gap-2"
                >
                  {checkingOut ? (
                    <RefreshCw className="h-4 w-4 animate-spin" />
                  ) : (
                    <DollarSign className="h-4 w-4" />
                  )}
                  Top Up ${topupAmount}.00 Credits
                </Button>
              </div>
            </CardContent>
          </Card>

          {/* Transaction Ledger Table */}
          <Card className="shadow-sm">
            <CardHeader className="flex flex-row items-center justify-between">
              <div>
                <CardTitle className="text-lg flex items-center gap-2">
                  <History className="h-5 w-5 text-primary" />
                  Cost Ledger & Financial Movements
                </CardTitle>
                <CardDescription>
                  Immutable double-entry log of budget reservations, actual reconciliations, refunds, and payments.
                </CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {transactions.length === 0 ? (
                <p className="text-sm text-muted-foreground py-6 text-center">
                  No financial movements recorded yet.
                </p>
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Type</TableHead>
                      <TableHead>Description</TableHead>
                      <TableHead>Amount (USD)</TableHead>
                      <TableHead>Balance After</TableHead>
                      <TableHead>Reserved After</TableHead>
                      <TableHead className="text-right">Timestamp</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {transactions.map((tx) => {
                      const isCredit = tx.amount_usd > 0;
                      return (
                        <TableRow key={tx.id}>
                          <TableCell>
                            <Badge
                              variant={
                                tx.entry_type === "credit_grant" || tx.entry_type === "stripe_payment"
                                  ? "secondary"
                                  : tx.entry_type === "reservation_hold"
                                  ? "outline"
                                  : "default"
                              }
                              className="text-xs uppercase"
                            >
                              {tx.entry_type.replace("_", " ")}
                            </Badge>
                          </TableCell>
                          <TableCell className="text-sm font-medium">
                            {tx.description}
                          </TableCell>
                          <TableCell className={`text-sm font-semibold ${isCredit ? "text-emerald-600 dark:text-emerald-400" : "text-muted-foreground"}`}>
                            {isCredit ? `+$${tx.amount_usd.toFixed(4)}` : `-$${Math.abs(tx.amount_usd).toFixed(4)}`}
                          </TableCell>
                          <TableCell className="text-sm font-mono text-muted-foreground">
                            ${tx.balance_after_usd.toFixed(4)}
                          </TableCell>
                          <TableCell className="text-sm font-mono text-muted-foreground">
                            ${tx.reserved_after_usd.toFixed(4)}
                          </TableCell>
                          <TableCell className="text-xs text-muted-foreground text-right">
                            {new Date(tx.created_at).toLocaleString()}
                          </TableCell>
                        </TableRow>
                      );
                    })}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </div>
      )}

      {activeTab === "pricing" && (
        <Card className="shadow-sm">
          <CardHeader>
            <CardTitle className="text-lg flex items-center gap-2">
              <DollarSign className="h-5 w-5 text-primary" />
              Active Provider Pricing Matrix
            </CardTitle>
            <CardDescription>
              Versioned rates applied to Gemini token generation, embeddings, and Tavily live search requests.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Provider</TableHead>
                  <TableHead>Operation</TableHead>
                  <TableHead>Model / Target</TableHead>
                  <TableHead>Unit Type</TableHead>
                  <TableHead>Input Rate (USD)</TableHead>
                  <TableHead>Output Rate (USD)</TableHead>
                  <TableHead>Request Rate (USD)</TableHead>
                  <TableHead className="text-right">Version</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {pricing.map((p) => (
                  <TableRow key={p.id}>
                    <TableCell className="font-semibold capitalize">{p.provider}</TableCell>
                    <TableCell className="text-sm">{p.operation_type.replace("_", " ")}</TableCell>
                    <TableCell className="font-mono text-xs">{p.model_name || "Any"}</TableCell>
                    <TableCell className="text-xs text-muted-foreground">{p.unit_type}</TableCell>
                    <TableCell className="font-mono text-sm">${p.input_rate_usd.toFixed(6)}</TableCell>
                    <TableCell className="font-mono text-sm">${p.output_rate_usd.toFixed(6)}</TableCell>
                    <TableCell className="font-mono text-sm">${p.fixed_request_rate_usd.toFixed(6)}</TableCell>
                    <TableCell className="text-right font-mono text-xs">v{p.version}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}

      {activeTab === "admin" && adminOverview && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <Card className="border-l-4 border-l-red-500">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs font-medium uppercase">Spent Today (System)</CardDescription>
                <CardTitle className="text-2xl font-bold">
                  ${adminOverview.global_spent_today_usd.toFixed(4)}
                  <span className="text-xs font-normal text-muted-foreground ml-2">
                    / ${adminOverview.global_daily_budget_usd.toFixed(2)}
                  </span>
                </CardTitle>
              </CardHeader>
            </Card>

            <Card className="border-l-4 border-l-indigo-500">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs font-medium uppercase">Spent This Month (System)</CardDescription>
                <CardTitle className="text-2xl font-bold">
                  ${adminOverview.global_spent_this_month_usd.toFixed(4)}
                  <span className="text-xs font-normal text-muted-foreground ml-2">
                    / ${adminOverview.global_monthly_budget_usd.toFixed(2)}
                  </span>
                </CardTitle>
              </CardHeader>
            </Card>

            <Card className="border-l-4 border-l-emerald-500">
              <CardHeader className="pb-2">
                <CardDescription className="text-xs font-medium uppercase">Total User Balances</CardDescription>
                <CardTitle className="text-2xl font-bold">
                  ${adminOverview.total_user_balances_usd.toFixed(2)}
                  <span className="text-xs font-normal text-muted-foreground ml-2">
                    ({adminOverview.total_user_wallets} wallets)
                  </span>
                </CardTitle>
              </CardHeader>
            </Card>
          </div>
        </div>
      )}
    </div>
  );
}

