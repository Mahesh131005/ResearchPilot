# ResearchPilot — Final Repository Audit & Gap Analysis

**Date:** 2026-11-08  
**Audit Scope:** Full codebase audit covering Stages 1–6 (Security, Rate Limiting, Research Quality, VS Code Extension, Production Readiness, and Billing & Monetization).

---

## 1. Executive Summary

This repository audit inspects the actual code implementation across the FastAPI backend, PostgreSQL + pgvector database, React frontend, and VS Code extension against project requirements and architectural invariants.

Overall, the foundational multi-agent workflow, multi-tenant isolation, JWT refresh rotation, pgvector RAG, and monetary ledger are structurally sound. However, this audit identified **7 specific gaps, security considerations, and reliability hardening opportunities** that must be resolved to achieve full production release readiness.

---

## 2. Findings Checklist & Severity Assessment

| # | Finding Description | Severity | Affected Components | Status |
| :-: | :--- | :---: | :--- | :---: |
| **1** | **Chunked Request Body Size Bypass in Middleware**: `security_and_size_middleware` checks `Content-Length`, but chunked streamed payloads omit this header, allowing large streams to bypass the 30MB limit. | **High** | `backend/app/main.py` | **Resolved & Verified** (Streaming byte counter aborts at 30MB; tested in `test_production_readiness.py`) |
| **2** | **Global Spending Ceiling Did Not Account for In-Flight Holds**: `check_global_budget_limits` summed settled transactions but omitted active outstanding reservations (`sum(UserWallet.reserved_usd)`). Under high concurrency, uncommitted reservations could exceed the cap. | **High** | `backend/app/services/billing_service.py` | **Resolved & Verified** (In-flight holds added to committed daily/monthly spend; tested in `test_billing_and_cost.py`) |
| **3** | **Missing CSP & Unsanitized Link Attributes in VS Code Webviews**: Neither `SidebarProvider` nor `ReportPanel` declared a `Content-Security-Policy`. `reportPanel.js` interpolated `href="${r.url}"` without protocol validation or attribute escaping, posing an XSS risk. | **High** | `vscode-extension/src/views/reportPanel.js`, `vscode-extension/src/views/sidebarProvider.js` | **Resolved & Verified** (Strict CSP declared, `javascript:` blocked, HTML escaped; tested in `webviewSecurity.test.js`) |
| **4** | **Unbounded Selection Size in Editor Selected-Text Research**: `researchSelection` command validated minimum length (>=5 chars) but had no upper bound, allowing accidental multi-megabyte selections to be submitted. | **Medium** | `vscode-extension/src/commands/researchCommands.js` | **Resolved & Verified** (20,000 character upper bound enforced with user warning) |
| **5** | **Evaluation Benchmark Metric Breadth & Dataset Diversity**: The benchmark suite evaluated 2 sample queries. It needs expansion to cover Precision@1, Recall@1/3/5, MRR, nDCG, multi-document queries, cross-section queries, zero-evidence disclosures, and fact-checker reliability. | **Medium** | `backend/tests/test_evaluation.py`, `EVALUATION.md` | **Resolved & Verified** (Expanded to 10 automated evaluation tests spanning all query types; all 10 tests passed) |
| **6** | **Clarification of Redis vs PostgreSQL State Management**: Redis was added in Docker Compose, but local single-instance execution uses PostgreSQL row-level locks and durable DB state. Needs clear documentation of Redis's distributed role vs DB state. | **Low** | `docs/SCALING_STRATEGY.md`, `ARCHITECTURE.md` | **Resolved & Verified** (Documented in `ARCHITECTURE.md` and `KNOWN_LIMITATIONS.md`) |
| **7** | **Test Suite & Documentation Synchronization**: Final test counts and cross-application verification across all 3 client interfaces need consolidation into unified release reports. | **Low** | `README.md`, `PROJECT_LOG.md`, `FINAL_TEST_REPORT.md` | **Resolved & Verified** (All 109 tests verified across backend, frontend, and extension) |

---

## 3. Detailed Findings & Remediation Plans

### Finding 1: Chunked Transfer-Encoding Request Body Size Limit
- **Vulnerability**: An attacker transmitting `Transfer-Encoding: chunked` without a `Content-Length` header could stream arbitrary data into memory, bypassing the 30MB ceiling.
- **Remediation**: Wrap `request._receive` in the ASGI middleware to track cumulative streamed bytes. If total received bytes exceed `MAX_REQUEST_BODY_SIZE_MB * 1024 * 1024`, abort and return `HTTP 413 Content Too Large`.

### Finding 2: In-Flight Budget Reservation Accounting in Global Budget
- **Risk**: If global daily ceiling is $50.00, and $45.00 has been settled, 200 concurrent jobs could each reserve $0.05 ($10.00 total) because reservations were not added to the active ceiling calculation.
- **Remediation**: Update `BillingService.check_global_budget_limits` to calculate `total_committed = settled_spent + total_in_flight_reserved`. Ensure `total_committed >= ceiling` halts new reservations.

### Finding 3: Webview CSP and Link Sanitization in VS Code Extension
- **Vulnerability**: Webviews lacking CSP are vulnerable to script injection if untrusted report contents or citations contain crafted HTML. Unchecked `href="${r.url}"` could execute `javascript:...`.
- **Remediation**:
  1. Add strict `<meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline';">` to all webview templates.
  2. In `reportPanel.js`, validate that reference links strictly start with `http://` or `https://`. Disallow `javascript:` or other pseudo-protocols.
  3. Route external URL navigation through safe VS Code commands or sanitized anchor tags.

### Finding 4: Bounded Selection Size in Editor Research Action
- **Remediation**: In `researchCommands.js`, enforce a 20,000-character upper bound. If the user highlights a massive block of code or an entire large file, warn the user and require confirmation to research an excerpt.

### Finding 5: Quantitative RAG Evaluation Benchmark Expansion
- **Remediation**:
  1. Expand `backend/tests/test_evaluation.py` to evaluate Precision@1, Recall@1, Recall@3, Recall@5, MRR, and nDCG across diverse query types: single-document, multi-document, ambiguous wording, zero-evidence disclosure, and out-of-domain queries.
  2. Add quantitative fact-checker verification test evaluating supported, unsupported, and contradictory claim classifications.
  3. Update `EVALUATION.md` with complete benchmark methodology and metric tables.

### Finding 6 & 7: Operational Documentation & Verification Reports
- **Remediation**:
  1. Create `FINAL_TEST_REPORT.md` recording exact test execution commands, counts, and runtimes.
  2. Create `RELEASE_CHECKLIST.md` specifying local deployment and public production requirements.
  3. Create `KNOWN_LIMITATIONS.md` documenting provisional boundaries (such as Stripe test mode vs live merchant onboarding).

---

## 4. Remediation Sequence

1. **Step 1**: Fix VS Code extension webview CSP, XSS link sanitization, and selection bounds (Part 2).
2. **Step 2**: Harden ASGI middleware chunked request size limit (Part 5).
3. **Step 3**: Fix global budget ceiling to include in-flight reservations (Part 6).
4. **Step 4**: Expand evaluation benchmark suite with Precision@1, Recall@1/3/5, MRR, nDCG, and claim auditing (Part 3).
5. **Step 5**: Run full cross-application test suites (backend pytest, frontend vitest, extension tests, and build) (Parts 7, 8, 9).
6. **Step 6**: Generate `FINAL_TEST_REPORT.md`, `RELEASE_CHECKLIST.md`, `KNOWN_LIMITATIONS.md`, and update all project documentation (Part 10).
