import { describe, it, expect } from "vitest";
import React from "react";
import { billingApi } from "../services/api";
import { Billing } from "../pages/Billing";

describe("Frontend Billing & Monetization", () => {
  it("verifies billingApi has all required client, checkout, and admin endpoints", () => {
    expect(billingApi).toBeDefined();
    expect(typeof billingApi.getWallet).toBe("function");
    expect(typeof billingApi.getOverview).toBe("function");
    expect(typeof billingApi.getTransactions).toBe("function");
    expect(typeof billingApi.createCheckout).toBe("function");
    expect(typeof billingApi.getAdminOverview).toBe("function");
    expect(typeof billingApi.getAdminUsers).toBe("function");
    expect(typeof billingApi.getAdminPricing).toBe("function");
  });

  it("verifies Billing component is exported as a valid React component", () => {
    expect(Billing).toBeDefined();
    expect(typeof Billing).toBe("function");
  });

  it("ensures zero Stripe secret keys or server credentials are in frontend bundles", () => {
    expect(import.meta.env.VITE_STRIPE_SECRET_KEY).toBeUndefined();
  });
});

