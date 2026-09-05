# 🛡️ AgentReady — Autonomous Agent-to-Agent Commerce Gateway

> **Track 1:** AI Growth & Agentic Commerce  
> **Event:** Razorpay AI Buildathon 2026  
> **Role:** AI Builder Intern Submission  
> **Status:** Working reference implementation using Razorpay Test Mode and simulated merchant protocol schemas

---

## Executive Summary

Autonomous AI agents can discover products, compare offers, negotiate, and assist users with purchases. However, allowing a probabilistic AI model to directly access payment execution introduces serious risks:

- Unauthorized spending
- Prompt injection
- Budget or quantity manipulation
- Duplicate transaction attempts
- Replay attacks
- Expired authorizations and quotes
- Inventory overselling

**AgentReady** is a policy-governed Agent-to-Agent (A2A) commerce gateway that separates AI intelligence from financial authority.

> **The LLM can propose, discover, and assist with negotiation. It must never directly control money movement. The Deterministic Payment Trust Engine has final authority.**

AgentReady combines AI-assisted commerce with deterministic transaction guardrails, stateful demo inventory reservation, idempotent order execution, persistent audit logging, and test-mode webhook reconciliation.

---

## What Broke at 2 AM

Building AgentReady exposed two important payment-system edge cases.

### 1. Idempotency non-determinism

Initially, the negotiation workflow created a random quote token for every attempt. When a buyer retried an identical purchase after a timeout, a new token generated a different transaction hash. This could bypass replay protection and create duplicate execution paths.

**Fix:** AgentReady now derives its SHA-256 idempotency key from a stable canonical transaction representation: the mandate, merchant, selected product, quantity, total amount in paise, currency, and normalized line-item context. Repeating the same transaction returns the original result rather than creating another order.

> If the current code uses `quote_id` in the key, replace this statement with the exact fields used by your implementation.

### 2. Float rounding in money calculations

The first implementation used floating-point values such as:

```text
₹2,400.00 × 10
```

Floating-point arithmetic can introduce precision errors in financial values.

**Fix:** AgentReady uses integer paise for critical financial data and policy validation:

```text
₹25,000.00 = 2,500,000 paise
₹599.40 = 59,940 paise
```

This keeps budget validation, quote calculation, ledger records, and Razorpay order amounts exact.

---

## Key Buildathon Features

### Natural-Language Intent Parsing

Users can describe their purchase requirements in natural language:

> “I need 10 mechanical wireless keyboards for my team under ₹25,000 from TechGear Store.”

The Buyer Agent converts the request into a typed purchase mandate containing:

- Product category
- Maximum budget in paise
- Target quantity
- Allowed merchants
- Expiry information
- Approval requirements, where applicable

When configured, the Buyer Agent uses OpenAI structured JSON output for intent extraction. A deterministic fallback parser keeps the application functional if the LLM is unavailable.

The LLM proposes intent only. It does not approve or execute payments.

### Agent-to-Agent Negotiation

The Buyer Agent submits an initial request or bid. The Merchant Agent then evaluates:

- Inventory availability
- Merchant discount policy
- Minimum-margin rules
- Quote expiry
- Cross-sell eligibility

The merchant can return a safe counter-offer, while deterministic rules prevent natural-language requests from overriding pricing boundaries.

### Dynamic Cross-Selling

AgentReady demonstrates a merchant-side revenue-growth workflow by recommending complementary products after a qualified purchase intent.

Example:

> “Complete your workspace: add 10× Pro Glide Desk Mats for ₹599.40 each.”

Cross-sell offers never silently modify the original purchase. Any modified transaction must pass through the same mandate and policy checks.

### Stateful Inventory Reservation

Inventory follows a controlled local demo workflow:

```text
AVAILABLE → RESERVED → SOLD
```

A valid quote reserves inventory for a defined time-to-live. If the quote expires, is cancelled, or is blocked before order creation, the reservation is released and inventory returns to `AVAILABLE`.

This prevents overselling and stale stock locks within the local demo inventory workflow.

### Razorpay Test-Mode and Webhook Reconciliation

When Razorpay test credentials are configured, AgentReady creates orders in **Razorpay Test Mode**.

For supported test webhook flows, the application verifies an HMAC SHA-256 signature before updating the local transaction ledger.

No real customer funds are processed.

---

## System Architecture

```text
┌────────────────────────────────────────────────────────┐
│ 1. AI BUYER INTENT PARSER                              │
│ Prompt: "Buy 10 keyboards under ₹25,000"               │
│ Output: Typed and bounded purchase mandate             │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ 2. MERCHANT AI PASSPORT & DEMO CATALOG                 │
│ -  /.well-known/ai-passport.json                        │
│ -  Machine-readable merchant capabilities               │
│ -  Stateful demo inventory and commerce policies        │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ 3. AGENT-ASSISTED QUOTE & STOCK RESERVATION            │
│ -  Buyer request / initial bid                          │
│ -  Merchant counter-offer within pricing limits         │
│ -  Temporary quote and stock reservation                │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ 4. DETERMINISTIC PAYMENT TRUST ENGINE                  │
│ [✓] Mandate expiry        [✓] Category scope           │
│ [✓] Quote expiry          [✓] Merchant allowlist       │
│ [✓] Budget cap            [✓] Integer paise validation │
│ [✓] Quantity cap          [✓] SHA-256 idempotency      │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ 5. RAZORPAY TEST-MODE ORDER CREATION                   │
│ -  Idempotent order request                             │
│ -  Test-mode order state tracking                       │
└───────────────────────────┬────────────────────────────┘
                            ▼
┌────────────────────────────────────────────────────────┐
│ 6. WEBHOOK RECONCILIATION & AUDIT LEDGER               │
│ -  HMAC SHA-256 verification, when configured           │
│ -  Persistent SQLite audit events                       │
└────────────────────────────────────────────────────────┘

GitHub Repository URL: [https://github.com/galetianand/AgentReady](https://github.com/galetianand/AgentReady)

5-min Pitch Video Link: [https://youtu.be/6zsDSQMiY5M](https://youtu.be/6zsDSQMiY5M)
```
