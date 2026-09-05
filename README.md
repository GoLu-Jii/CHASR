# CHASR

**A B2B invoice-recovery agent for the period after an invoice goes overdue.**

Built for Razorpay's AI Buildathon 2026 — Track 3: AI Revenue Recovery.

CHASR turns a customer's reply into a structured payment commitment, scores that customer's reliability from their own promise-keeping history, applies a deterministic escalation policy, and records every step in a hash-chained audit ledger. It's local-first: the dashboard, seeded data, demo clock, escalation policy, reliability scoring, audit verification, and results screen all work with zero API keys. Two integrations are optional on top of that — Groq for live reply extraction, and Razorpay test-mode for real payment links.

## Table of contents

- [Why this exists](#why-this-exists)
- [What works without credentials](#what-works-without-credentials)
- [Architecture at a glance](#architecture-at-a-glance)
- [Tech stack](#tech-stack)
- [Quick start](#quick-start)
- [Try the demo](#try-the-demo)
- [Reliability model — honest numbers](#reliability-model--honest-numbers)
- [Verify the project](#verify-the-project)
- [Optional ML workflow](#optional-ml-workflow)
- [Known limitations](#known-limitations)
- [What this isn't claiming](#what-this-isnt-claiming)
- [Safety notes](#safety-notes)
- [Docs](#docs)
- [License](#license)

## Why this exists

Once a B2B invoice goes overdue, recovery today is either a person manually chasing every account — which doesn't scale — or a fixed-schedule script blasting the same reminder at everyone, which treats a reliable long-term customer and a repeat defaulter identically and tracks none of what was actually promised. CHASR puts a bounded, auditable decision process in that gap: the right tone, at the right time, for the right customer, with a record of every step that can be checked later.

This isn't a claim that the underlying mechanism is new — accounts-receivable automation is a mature category at enterprise scale (HighRadius and others already publish results there). What's specific here is the intersection: sized for the MSME selling to another MSME, not the enterprise-to-enterprise case existing tools and platforms like TReDS already cover.

## What works without credentials

After setup, the dashboard, seeded data, demo clock, escalation policy, reliability scoring, audit verification, and results screen all run locally with no API keys.

- **Groq (`GROQ_API_KEY`)** — needed only for the **Record customer reply** screen. CHASR deliberately does not fabricate a payment commitment when the LLM is unavailable; the screen simply won't extract anything without it.
- **Razorpay (`RAZORPAY_KEY_ID` / `RAZORPAY_KEY_SECRET`)** — optional, test-mode only. Without credentials, Razorpay actions use a clearly marked mock fallback rather than silently pretending to succeed.

## Architecture at a glance

| Component | Job | Uses an LLM? |
|---|---|---|
| **Escalation** | Decides the tone for an overdue invoice — nudge, firm, or formal — from invoice age, reliability score, pending commitments, and stopping rules | No — fully deterministic |
| **Promise extraction** | Reads a customer's reply and pulls a structured commitment (amount, date, confidence), or honestly returns nothing rather than guessing | Yes — the only LLM call in the system |
| **Reliability scoring** | Scores 0–1 how likely a customer is to follow through, from that customer's own promise history | No — scikit-learn logistic regression |
| **Audit ledger** | Append-only, hash-chained record of every event, so the sequence of decisions can be independently verified later | No |

## Tech stack

- FastAPI, SQLAlchemy, and SQLite
- React 19 and Vite
- Groq JSON-mode extraction (optional)
- scikit-learn reliability scoring
- Razorpay test-mode integration with an explicit offline mock fallback
- Per-invoice SHA-256 append-only audit chains

## Quick start

### 1. Prerequisites

- Python 3.10+
- Node.js 20+ and npm
- Git (to clone the repository)

### 2. Clone and configure the backend

```bash
git clone <your-repository-url>
cd CHASR

python -m venv .venv
```

Activate the virtual environment and install the Python dependencies:

```bash
# Windows PowerShell
.\.venv\Scripts\Activate.ps1

# macOS/Linux
source .venv/bin/activate

pip install -r requirements.txt
```

Copy the environment template:

```bash
# Windows PowerShell
Copy-Item .env.example .env

# macOS/Linux
cp .env.example .env
```

`DATABASE_URL` already points to the included SQLite demo database. Add credentials only if you need the optional integrations:

```dotenv
GROQ_API_KEY=your_groq_key                 # enables live reply extraction
RAZORPAY_KEY_ID=your_razorpay_test_key     # optional; test mode only
RAZORPAY_KEY_SECRET=your_razorpay_secret   # optional; test mode only
```

Start the API from the repository root:

```bash
uvicorn backend.main:app --reload --port 8000
```

On its first start, CHASR creates compatible SQLite tables and seeds its deterministic demo invoices. Confirm it is running at [http://localhost:8000/api/health](http://localhost:8000/api/health), or explore the API at [http://localhost:8000/docs](http://localhost:8000/docs).

### 3. Start the frontend

Open a second terminal in the repository root:

```bash
cd frontend
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` and `/demo` requests to the backend at port 8000, so no frontend environment file is required for local development.

> On Windows systems that block PowerShell scripts, run `npm.cmd install` and `npm.cmd run dev` instead. You can also run the virtual environment interpreter directly, for example `& .\.venv\Scripts\python.exe -m uvicorn backend.main:app --reload --port 8000`.

## Try the demo

1. Visit **Collections** to inspect the seeded invoice watchlist and reliability scores.
2. Open an invoice to create/sync a payment link and verify its audit-ledger chain. Without Razorpay credentials, these use the safe mock fallback.
3. Visit **Customer reply**, select an invoice, and submit a reply such as `We can release 50% next Wednesday and the balance after our customer settles.` With Groq configured, the app extracts validated tranches and dates.
4. Use the **+1 day** and **+7 days** controls to advance the persisted virtual clock and immediately evaluate escalation outcomes.
5. Use **Reset** to restore the hand-authored demo slice and return the virtual clock to today. It does not reset the wider synthetic training history.

The escalation ladder is deterministic: nudge → firm → formal. Reliability changes the *timing* of escalation, not the available policy actions. Vague or incomplete commitments are flagged for human review instead of receiving invented terms.

## Reliability model — honest numbers

Trained with a customer-level train/test split (never by invoice, so a customer's other promises can't leak into their own held-out evaluation):

```
Dataset Split: 695 Train Customers, 298 Test Customers
Row Counts:    8194 Train Promises, 3394 Test Promises

--- Model Evaluation (Held-out Customers) ---
ROC-AUC:   0.721
Precision: 0.807
Recall:    0.611

              precision    recall  f1-score   support
  Broken (0)       0.48      0.71      0.57      1140
    Kept (1)       0.81      0.61      0.70      2254
    accuracy                           0.64      3394
```

Read plainly: the model is better at *catching* broken promises than being *precise* about them (0.71 recall vs. 0.48 precision on the Broken class) — it over-flags risk more than it misses it. That's a defensible trade-off for a collections tool, but it's a trade-off, not a strength to gloss over. This is synthetic-data validation of the pipeline, not a production-performance claim.

## Verify the project

From the repository root, run backend tests:

```bash
python -m pytest backend/tests -q
```

Build the frontend from `frontend/`:

```bash
npm run build
npm run lint
```

The current test suite covers payment allocation, escalation behavior, missing configuration, and ledger tamper detection. The lint command may report existing React hook/style warnings; these are warnings rather than build failures.

## Optional ML workflow

The repository includes a trained reliability model at `backend/ml/reliability_model.joblib`. To retrain it against the SQLite data configured in `.env`:

```bash
python -m backend.ml.train_reliability_model
```

## Known limitations

- **The audit ledger is tamper-evident, not tamper-proof.** Each entry stores the hash of the previous entry, and verification recomputes that chain live — this catches a quiet edit to a single row. It does **not** protect against someone with full database access rewriting the entire chain and recomputing every hash to stay internally consistent. The fix for that is an external, independently-controlled checkpoint (e.g. committing the ledger's hash to git on a schedule) — not implemented yet.
- **The reliability model is trained on synthetic data.** Its precision/recall/ROC-AUC numbers above validate that the training pipeline works correctly end to end; they are not a claim about real-world collections performance.
- **Razorpay integration is test-mode only** and falls back to a clearly marked mock when credentials or network access aren't available — it never silently pretends a real payment object was created.

## What this isn't claiming

- Not a claim that AR automation / promise-to-pay tracking is a new mechanism — it's proven at enterprise scale elsewhere.
- Adjacent to Razorpay's Smart Collect, not the same thing — Smart Collect reconciles money that's already arrived; CHASR acts before that point.
- Not a claim that no one does AI-driven collections outreach anywhere — specifically, that the enterprise AR category (e.g. HighRadius) doesn't run AI voice conversations, which is a narrower and independently checkable claim.

## Safety notes

- Use Razorpay **test-mode** credentials only; this project is a prototype.
- Keep `.env` private. It is ignored by Git and should never contain production credentials.
- The audit ledger is tamper-evident within the application, not externally notarized.

## Docs

- [`docs/00_PROJECT_BRIEF.md`](docs/00_PROJECT_BRIEF.md) — product scope and positioning
- [`docs/01_BUILD_SPEC.md`](docs/01_BUILD_SPEC.md) — implementation details
- [`docs/decisions.md`](docs/decisions.md) — known limitations and design decisions

## License

No license has been chosen yet — this is a hackathon submission. Add a `LICENSE` file before reusing or distributing this code outside that context.