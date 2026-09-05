# CHASR Decision Record

This document records the important product, architecture, data, ML, payment, UX, and operational decisions in CHASR. It explains why each choice was made, what alternative was rejected, and what limitation remains. It describes the current implementation, not only the original build plan.

## 1. Product Decisions

### 1.1 Target MSME-to-MSME receivables

**Decision:** CHASR targets overdue B2B invoices for a small-business collections operator selling to another small or medium business.

**Why:** This is a narrower and more defensible problem than attempting to build a general accounts-receivable platform. The target user needs prioritization, promise tracking, and an audit trail without enterprise AR complexity.

**Alternative rejected:** A broad multi-tenant enterprise collections product. That would require authentication, tenant isolation, permissions, production deployment, and a much larger workflow surface.

### 1.2 Four functional engines

**Decision:** The product is split into deterministic escalation, LLM promise extraction, ML reliability scoring, and a hash-chained audit ledger.

**Why:** Each tool is used for the kind of problem it handles best:

- Rules decide policy and timing.
- The LLM interprets unstructured customer language.
- ML estimates customer reliability from historical outcomes.
- The ledger records what happened and when.

This separation makes the system easier to explain and test.

**Alternative rejected:** One general-purpose AI agent deciding everything. That would make policy less predictable, harder to test, and difficult to defend when an escalation decision is questioned.

### 1.3 Keep non-MVP features out

**Decision:** Multi-tenant authentication, multi-currency support, voice calls, real WhatsApp/SMS delivery, automatic legal action, and pooled cross-business reputation are out of scope.

**Why:** They add substantial operational and compliance complexity without strengthening the core demo: promise extraction, reliability-aware escalation, payment reconciliation, and auditability.

**Tradeoff:** The current system is a focused prototype rather than a production collections platform.

### 1.4 Use English templates for the MVP

**Decision:** Escalation templates are written in English and outbound WhatsApp/SMS delivery is simulated and logged.

**Why:** Real channel delivery requires WhatsApp Business verification, TRAI DLT registration, message-template approval, and a registered business identity. The prototype can still demonstrate the message that would be sent, its timing, and its audit record.

**Alternative rejected:** Pretending that a message was delivered. The system explicitly labels delivery as simulated.

**Future direction:** Hinglish and real WhatsApp/UPI workflows belong in a later product phase.

## 2. Backend Architecture Decisions

### 2.1 FastAPI for the API

**Decision:** Use Python and FastAPI for the backend.

**Why:** FastAPI gives typed request handling, clear HTTP endpoints, automatic API documentation, and a small implementation footprint suitable for an engine-oriented prototype.

**Alternative rejected:** A larger framework such as Django. Its admin and full-stack features were unnecessary for this MVP.

### 2.2 SQLite and SQLAlchemy

**Decision:** Use SQLite accessed through SQLAlchemy.

**Why:** SQLite is zero-configuration, local, portable, and sufficient for a deterministic demo and offline evaluation dataset. SQLAlchemy provides relationships and a path to a different relational database later.

**Alternative rejected:** A hosted database. It would add credentials, deployment dependencies, and network failure modes to a local demo.

**Tradeoff:** SQLite is not the intended production choice for concurrent multi-tenant workloads.

### 2.3 Manual endpoint ownership in `main.py`

**Decision:** The current API endpoints and much of the response/policy wiring live in `backend/main.py`.

**Why:** This kept the prototype moving quickly while the domain engines remained separate.

**Alternative intended by the build spec:** Separate routers for invoices, simulation, results, and demo operations.

**Known deviation:** The `backend/routers/` modules exist but are currently empty; the routes are not yet split into those modules. This is an organizational debt, not a behavioral feature.

### 2.4 Local development CORS only

**Decision:** CORS permits only the local Vite origins `localhost:5173` and `127.0.0.1:5173`.

**Why:** The application is intended for local development and demo recording. Restricting origins avoids opening the development API broadly.

**Tradeoff:** A deployed frontend would need an explicit production origin configuration.

### 2.5 Environment-based secrets

**Decision:** Groq and Razorpay credentials are loaded from the root `.env` through `python-dotenv`.

**Why:** Secrets do not belong in source code or committed configuration.

**Operational rule:** Credentials must be rotated if exposed and `.env` must remain ignored by Git.

## 3. Domain and Data Model Decisions

### 3.1 Invoice state includes partial payment

**Decision:** Invoices use `unpaid`, `partially_paid`, `paid`, `written_off`, and `escalation_exhausted` states.

**Why:** Payment recovery is not binary. Partial receipts must remain visible and must continue through the recovery workflow until the invoice is sufficiently settled or handed to a human.

**Payment thresholds:**

- At least 95 percent of the invoice amount means `paid`.
- A positive amount below 95 percent means `partially_paid`.
- Zero received keeps the prior unpaid state.

**Alternative rejected:** Marking any receipt as paid. That would hide remaining exposure.

### 3.2 Promise records are separate from invoice status

**Decision:** A promise stores amount, promised date, confidence, source text, and its own status: `pending`, `kept_full`, `kept_partial`, or `broken`.

**Why:** An invoice can have multiple commitments or tranches, and invoice payment status alone cannot explain whether each commitment was fulfilled.

**Tradeoff:** Promise allocation requires explicit reconciliation logic and careful handling of duplicate or incomplete commitments.

### 3.3 Customer reliability is append-only history

**Decision:** Reliability scores are stored as historical rows rather than overwriting one current row per customer.

**Why:** Keeping score snapshots preserves how the system viewed a customer over time and supports auditability.

**Alternative rejected:** Updating a single score row. That is simpler but loses historical model outputs.

### 3.4 Demo data is a separate deterministic slice

**Decision:** Hand-authored demo customers use IDs in the `10101` to `10115` range, while generated synthetic history remains outside that slice.

**Why:** Resetting the demo should not destroy the larger training/evaluation dataset. The recording state also needs recognizable, varied scenarios.

**Current variety includes:** paid, partially paid, unpaid, written-off, disputed, vague, formal, nudge, and multi-tranche cases.

### 3.5 Re-seed the demo for repeatability

**Decision:** `/demo/reset` removes demo invoices, promises, ledger entries, reliability rows, and customers, resets the virtual clock, and recreates the hand-authored dataset.

**Why:** A recorded demo needs a known starting state after experimentation.

**Tradeoff:** Reset is destructive for the demo slice by design. It does not target the general synthetic history.

### 3.6 Synthetic data is for training and evaluation, not production truth

**Decision:** The generated dataset simulates customer behavior, promise outcomes, and payment history.

**Why:** There is no production customer history in a hackathon prototype. Synthetic data allows the model and evaluation pipeline to run end to end.

**Limitation:** Synthetic results are evidence that the pipeline works, not proof of production recovery performance.

**Known deviation:** The generator uses random distributions without globally seeding Python and NumPy. Repeatability is guaranteed for the hand-authored demo reset, not necessarily for regenerating the large synthetic dataset.

## 4. Escalation and Policy Decisions

### 4.1 Deterministic escalation ladder

**Decision:** Escalation follows `nudge -> firm -> formal` using configured overdue-day thresholds and reliability bands.

**Why:** Policy must be explainable and reproducible. The same state should produce the same action.

**Alternative rejected:** Asking the LLM to choose escalation severity. LLM output can vary and would make compliance and testing harder.

### 4.2 Reliability changes timing, not policy meaning

**Decision:** Reliability adjusts when a customer reaches firm or formal escalation, while the available stages remain fixed.

**Why:** This keeps the policy bounded. A low-reliability customer can be contacted sooner, but the system does not invent arbitrary actions.

**Configured examples:**

- Default firm/formal thresholds: 15/30 overdue days.
- Low-reliability thresholds: 7/21 days.
- High-reliability thresholds: 20/35 days.

### 4.3 Promise stopping rule

**Decision:** A dated pending promise pauses automated escalation while it is within the promised date plus the configured grace period.

**Why:** Continuing to send reminders during an agreed payment window would contradict the customer’s commitment and create unnecessary contact.

### 4.4 Expired commitments escalate without changing dates

**Decision:** When a dated pending promise passes its grace period, it becomes broken and triggers escalation. The original promised date is never rewritten. Severity stays reliability-aware: a customer at or below the low-reliability threshold escalates to `formal` immediately, while a higher-reliability customer gets one `firm` chance before formal.

**Why:** The date is historical evidence of what the customer said. Advancing the demo clock must evaluate that evidence, not alter it. Keeping the reliability-aware rule here preserves the reliability gradient (§4.2) even in the hard "broken promise" case instead of collapsing everyone to the same stage.

**Multiple-promise rule:** Every pending commitment is evaluated. An expired dated promise can trigger escalation even if another commitment is incomplete and requires human review.

### 4.5 Incomplete commitments require human review

**Decision:** A commitment without a concrete date sets `needs_review` and pauses normal automation, unless another dated commitment has already expired and requires escalation.

**Why:** The system should not invent a schedule for an ambiguous promise.

### 4.6 Contact ceiling and observation window

**Decision:** Automated contacts are capped at six per invoice. After formal escalation, ten days without response can move the invoice to human review.

**Why:** Automation must stop instead of becoming harassment or an infinite reminder loop.

### 4.7 Simulated channel output

**Decision:** Escalation creates and logs the message that would be sent, with `WhatsApp (Simulated)` as the channel.

**Why:** The decision and audit behavior can be demonstrated without claiming that a real message was delivered.

## 5. LLM Decisions

### 5.1 Groq only for promise extraction

**Decision:** Groq is used only to interpret customer replies.

**Why:** Natural-language interpretation is the part of the workflow that benefits from an LLM. Escalation and payment policy remain deterministic.

### 5.2 Strict JSON contract

**Decision:** The prompt requests JSON containing `has_commitment` and commitment objects with amount, promised date, and confidence.

**Why:** A narrow contract makes model output easier to validate and persist than free-form prose.

### 5.3 Relative dates and percentages are resolved by the model

**Decision:** The prompt supplies the invoice amount and virtual current date, asking the model to resolve phrases such as “50 percent next Wednesday” into numeric amounts and ISO dates.

**Why:** The model can interpret language contextually while the application still validates the result.

### 5.4 No regex fallback

**Decision:** Invalid or missing model output remains empty or null rather than being guessed through regular expressions.

**Why:** A recovery system must not claim a customer promised a number or date that was not actually extracted with sufficient confidence.

**Tradeoff:** The live extraction flow requires `GROQ_API_KEY`; offline mode cannot produce a fake successful extraction.

### 5.5 Validate and sanitize model output

**Decision:** Amounts above the invoice total, non-positive amounts, invalid confidence values, malformed JSON, and invalid dates are rejected or normalized.

**Why:** Model output is untrusted input and must not directly mutate financial state.

### 5.6 Avoid duplicate pending promises

**Decision:** Reprocessing the same reply with the same amount and promised date reuses an existing pending promise instead of inserting another identical promise.

**Why:** Repeated UI submissions should not inflate the customer’s obligations or create misleading duplicate rows.

## 6. ML Decisions

### 6.1 Logistic regression for reliability

**Decision:** Use a scaled, class-balanced scikit-learn Logistic Regression pipeline.

**Why:** Logistic regression is lightweight, interpretable, produces a probability-like output, and is appropriate for a small tabular feature set.

**Alternative rejected:** A deep neural model. It would add complexity and reduce explainability without a demonstrated data benefit.

### 6.2 Customer-level train/test split

**Decision:** Training and held-out evaluation split by customer, not by invoice.

**Why:** Splitting invoices from the same customer across train and test would leak customer behavior and overstate generalization.

### 6.3 Reliability feature set

**Decision:** The trained model uses historical promise counts, kept-full/partial/broken counts, kept rate, broken rate, and average days late.

**Why:** These features directly represent the behavior the score is intended to estimate.

### 6.4 Neutral cold start

**Decision:** A customer with no promise history receives a neutral score of `0.5`.

**Why:** There is no evidence supporting a high or low reliability judgment for a new customer.

### 6.5 Small responsiveness calibration

**Decision:** Reply responsiveness is computed live and contributes 10 percent of the final score after the seven-column model prediction.

**Why:** Responsiveness is useful at runtime but was not part of the already-trained model feature contract. A bounded calibration incorporates it without retraining during a request.

**Limitation:** This is a transitional design. A future retraining run could include responsiveness directly in the model.

### 6.6 Reliability drives targeting and escalation

**Decision:** The score is used both by the escalation timing policy and by held-out adaptive targeting.

**Why:** This connects the model output to observable product behavior instead of displaying a score with no consequence.

### 6.7 Honest evaluation over invented uplift

**Decision:** The results page reports observed recovery once and uses precision/recall plus target-set comparison. Model and baseline recovery fields intentionally share the observed amount, and uplift is zero.

**Why:** The historical data has no counterfactual outcome showing what would have happened under a different reminder schedule. Claiming causal uplift would be misleading.

## 7. Payment and Razorpay Decisions

### 7.1 Razorpay SDK isolation

**Decision:** All Razorpay API access is isolated in `backend/integrations/razorpay_client.py`.

**Why:** Provider-specific behavior should not be scattered through policy code or route handlers.

### 7.2 Test mode only

**Decision:** Credentials are read from environment variables and the intended integration is Razorpay test mode.

**Why:** The demo must show realistic provider rails without moving real money.

### 7.3 Payment links use remaining or committed amount

**Decision:** A new payment link uses the remaining invoice balance, or the next pending commitment tranche when one is stated.

**Why:** A customer promising 50 percent should not be shown a checkout request for the full invoice amount when the workflow is explicitly tranche-aware.

### 7.4 Reuse provider links

**Decision:** Once a payment-link ID exists on an invoice, later requests reuse it.

**Why:** Repeated clicks should not create unlimited provider objects or exhaust Razorpay test-mode quotas.

### 7.5 Explicit mock fallback

**Decision:** If Razorpay is unavailable, the integration returns a marked mock object. Provider failures are surfaced by the API rather than silently presented as a successful live object.

**Why:** Local development should remain usable, but the demo must not confuse a mock URL with a real Razorpay object.

### 7.6 Cumulative payment reconciliation

**Decision:** Provider payment sync treats the received amount as cumulative, records only the positive delta in the ledger, and updates invoice status from the cumulative total.

**Why:** Provider status polling may return the total paid so far rather than a new transaction amount.

### 7.7 Allocate receipts across commitments

**Decision:** Cumulative receipts are allocated across commitments in insertion order. A full invoice payment resolves all remaining commitments; partial receipts can mark individual commitments partially kept.

**Why:** This gives multi-tranche invoices a deterministic relationship between money received and promise outcomes.

**Tradeoff:** Insertion order is a practical MVP rule. A production system would likely require explicit tranche ordering, provider transaction IDs, and stronger reconciliation semantics.

## 8. Audit and Integrity Decisions

### 8.1 Append-only application write path

**Decision:** Ledger entries are added through `ledger.append_entry()` and are not updated through normal application flows.

**Why:** Centralizing writes makes event creation and hash chaining consistent.

### 8.2 Per-invoice SHA-256 chain

**Decision:** Each invoice has an independent chain beginning with 64 zeroes. Each hash covers the previous hash, sorted JSON payload, and timestamp.

**Why:** Per-invoice verification is simple to explain and lets the UI show a focused audit timeline.

**Alternative rejected:** One global chain. It would couple unrelated invoices and make isolated inspection less convenient.

### 8.3 Verify on demand

**Decision:** Invoice detail provides a Verify Integrity action that recomputes the chain.

**Why:** The user can demonstrate trust verification at the moment an invoice is reviewed without adding constant background work.

### 8.4 Known integrity limit

**Decision:** Treat the chain as tamper-evident, not as an immutable external authority.

**Why:** An administrator with full database access could rewrite the entire chain. The system documents this limitation rather than overstating the guarantee.

**Future hardening:** Externally notarize or commit the latest ledger hash outside the database.

## 9. Virtual Clock and Demo Operations

### 9.1 Persist one day offset

**Decision:** Demo time is real UTC plus a single persisted SQLite day offset.

**Why:** This is enough to compress overdue behavior for a recording without building a general time-travel framework.

### 9.2 Only allow one- and seven-day jumps in the UI/API flow

**Decision:** The demo controls expose `Advance +1 Day` and `Advance +7 Days`.

**Why:** Fixed jumps keep the rehearsal predictable and prevent an overly elaborate calendar tool from becoming part of the product.

### 9.3 Rerun escalation immediately

**Decision:** Advancing the clock immediately evaluates active demo invoices.

**Why:** The recording should visibly show the mechanism changing state rather than waiting for a real cron process.

### 9.4 Reset time with demo data

**Decision:** Demo reset returns the virtual clock to zero before reseeding.

**Why:** A clean fixture requires both data and time to be known.

### 9.5 Demo mode visibility

**Decision:** The current frontend shows the demo bar unless `VITE_DEMO_MODE` is explicitly set to `false`.

**Why:** This makes the local recording workflow work without requiring an extra environment setting.

**Known deviation:** The original spec described demo mode as opt-in with `VITE_DEMO_MODE=true`. The current implementation is effectively opt-out for local convenience.

## 10. Frontend and UX Decisions

### 10.1 React and Vite

**Decision:** Use React with Vite and a small manual client-side route switch.

**Why:** The app has only four screens and a lightweight route map is sufficient for the prototype.

**Alternative rejected:** React Router. It would be reasonable for a larger app, but it was not necessary for the current surface.

### 10.2 Four operational screens

**Decision:** Provide dashboard, invoice detail, simulation, and results screens.

**Why:** These map directly to the collection workflow and the demo narrative.

### 10.3 Manual history navigation

**Decision:** Use `history.pushState` and `popstate` rather than a routing dependency.

**Why:** It keeps navigation dependency-free and matches the small number of views.

**Tradeoff:** Route behavior, loading boundaries, and error boundaries are less structured than with a mature router.

### 10.4 Operations-console visual language

**Decision:** Use a quiet light console palette, compact metrics, bordered panels, INR formatting, and visible buttons.

**Why:** Collections operators need scanning, comparison, and repeated actions more than marketing-style decoration.

### 10.5 Shared button affordances

**Decision:** Global button styles provide borders, hover states, focus rings, disabled states, and primary/secondary variants.

**Why:** Plain text-looking actions caused ambiguity in the original UI, especially for demo controls and payment actions.

### 10.6 Show system state after actions

**Decision:** Demo controls and payment sync show progress or status notices, and simulation exposes payment status, amount received, and the next CHASR action.

**Why:** A user needs confirmation that an action changed the system. Silent network requests created the earlier blank or confusing states.

### 10.7 Single source of truth for the next action

**Decision:** The escalation engine owns `next_action(session, invoice)`, a read-only preview of what the scheduler would do next (terminal, broken/expired promise, incomplete commitment, or the reliability-adjusted ladder). The dashboard and invoice detail render this directly instead of re-implementing policy.

**Why:** The UI previously duplicated the escalation preconditions in `main.py` and could drift from real policy — most notably `_next_action` masked an expired promise whenever a companion no-date promise existed, showing "Human review required" instead of the broken-commitment action that would actually fire.

**How it behaves:** Broken and expired commitments are surfaced first, so an expired date is never hidden behind an uncertain promise. The dashboard therefore shows precisely what the next scheduler pass will do.

### 10.7 Indian locale formatting

**Decision:** Use INR currency formatting and Indian date formatting in the frontend.

**Why:** The product context is Indian MSME collections and Razorpay test payments.

### 10.8 Preserve raw audit payloads

**Decision:** Show ledger payload JSON in the invoice timeline.

**Why:** The MVP values inspectability and demo transparency over a fully polished audit viewer.

**Tradeoff:** Raw JSON is less approachable for non-technical users.

## 11. Testing Decisions

### 11.1 In-memory engine tests

**Decision:** Engine tests use in-memory SQLite databases.

**Why:** They are fast, isolated, and test escalation, ledger, and payment logic without mutating the development database.

### 11.2 Regression tests for observed failure modes

**Decision:** Tests cover payment allocation, duplicate commitments, expired commitments, incomplete commitments, and date immutability.

**Why:** These were high-risk cross-state failures discovered during demo rehearsal.

### 11.3 Build and static diagnostics

**Decision:** Validate with backend pytest, frontend Vite build, frontend lint, and editor diagnostics.

**Why:** The product crosses Python API and React build boundaries, so both must be checked.

### 11.4 Known test gaps

The current repository does not yet have:

- A browser end-to-end test.
- A mocked Groq contract test for exact extraction responses.
- A mocked Razorpay SDK contract test for live payloads and provider errors.
- A full startup/seed/reset integration test.
- Assertions in `test_reliability_split.py`; it currently documents the intended split but does not execute a test.

These are deliberate remaining hardening opportunities, not claims that the current unit tests cover every deployment path.

## 12. Known Implementation Deviations

These points are recorded to prevent accidental overclaiming:

1. The route modules under `backend/routers/` are currently empty; endpoint definitions remain in `main.py`.
2. `main.py` loads a model into `ml_model`, but inference is actually performed by the lazy-loaded model in `engines/reliability.py`.
3. The implementation uses `backend/ml/reliability_model.joblib`, not the `ml/model.pkl` name from the original specification.
4. The live inference responsiveness calibration is not part of the trained model feature vector.
5. The current inference feature computation uses all persisted customer promises rather than explicitly truncating history at a prediction timestamp.
6. Synthetic data generation is not globally seeded; only the hand-authored demo reset is designed to be repeatable.
7. Razorpay test-mode quotas can prevent new provider objects even when credentials are valid. Existing payment links are reused and provider errors should be shown honestly.
8. The results page does not claim causal recovery uplift because the data has no counterfactual policy outcomes.
9. The audit chain is tamper-evident within the application, not externally notarized.
10. Current frontend lint output contains non-blocking React hook/style warnings; production build and static diagnostics remain separate validation gates.
