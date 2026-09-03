# CHASR — Build Spec for Code-Writer AI

Read `00_PROJECT_BRIEF.md` first for context on *why*. This file is the *what to build*.

## 0. Before writing anything

These files already exist in the repo and are considered **done** for MVP purposes:

```
config.py
database.py
models.py
engines/ledger.py
engines/escalation.py
engines/promise_extraction.py
data/generate_synthetic.py
ml/train_reliability_model.py
```

**Open and read every one of these before writing new code.** Match their existing naming conventions, imports, and patterns exactly. Do not rewrite, restructure, or "improve" them — only touch one if it has a bug that's actually blocking integration, and say so explicitly if you do.

## 1. MVP scope — what's in, what's out

**In scope:**
- All four engines running end-to-end against the synthetic dataset
- Real Razorpay test-mode Invoice / Payment Link creation
- Hash-chained audit ledger with a live "verify integrity" check
- A batch evaluation run: recovered amount, precision/recall, honest exception list, vs. a dumb fixed-schedule baseline
- Four frontend screens, plus a small demo-control bar (§6)

**Explicitly out of scope:**
- Real WhatsApp/SMS delivery — simulated and logged
- Voice/call-based collection
- Actual legal escalation — the system flags for human review, never acts on the flag itself
- Multi-tenant auth, multi-currency, production deployment concerns
- Any "pooled reliability across businesses" feature — that's future vision only, see brief

## 2. Stack (confirmed, do not substitute)

| Layer | Choice |
|---|---|
| Backend | Python + FastAPI |
| Database | SQLite |
| LLM (promise extraction only) | Groq API, the llama model already configured in `config.py` |
| ML (reliability score) | scikit-learn `LogisticRegression` |
| Payments | Razorpay test-mode — Invoices API + Payment Links |
| Frontend | React + Vite |
| Config | `python-dotenv`, reading from a `.env` in project root |

**Environment variables** (already the standard — do not introduce others):
```
GROQ_API_KEY=
RAZORPAY_KEY_ID=
RAZORPAY_KEY_SECRET=
```
No paid API keys are in use anywhere in this project. If a task seems to need one, stop and flag it instead of adding it.

## 3. Data model (SQLite) — unchanged, build to this exactly

```sql
customers (
  id, name, gstin, phone, email, created_at
)

invoices (
  id, customer_id FK, amount, due_date, issued_date,
  razorpay_invoice_id,
  status        ENUM(unpaid, partially_paid, paid, written_off),
  current_stage ENUM(none, nudge, firm, formal),
  last_contacted_at,
  contact_count            -- for the 6-contact hard ceiling, §5
)

ledger (                        -- append-only, never UPDATE/DELETE
  id, invoice_id FK,
  event_type ENUM(
    invoice_created, escalation_sent, reply_received,
    promise_extracted, promise_status_updated,
    payment_link_created, payment_received,
    escalated_to_human_review
  ),
  payload JSON,
  created_at,
  prev_hash, hash              -- sha256(prev_hash + json(entry)), chained
)

promises (
  id, invoice_id FK, ledger_entry_id FK,
  amount, promised_date,
  confidence ENUM(firm, soft, vague),
  status     ENUM(pending, kept_full, kept_partial, broken),
  source_text
)

customer_reliability (
  customer_id FK, computed_at,
  total_promises, kept_full, kept_partial, broken,
  kept_full_rate FLOAT, broken_rate FLOAT,
  avg_days_late, score FLOAT    -- model output, 0 to 1
)
```

If `models.py` already implements this with minor naming differences, defer to what's already there.

## 4. Remaining components — build these

### `backend/engines/reliability.py`
- **Do:** compute features live from `ledger`/`promises` at inference time (kept_full_rate, broken_rate, avg_days_late, total_promises, a responsiveness signal from reply history). Load the trained model from `ml/model.pkl` once at startup. Expose one clean function, e.g. `score_customer(customer_id, db) -> float`. For a brand-new customer with zero promise history, return a documented neutral default (e.g. 0.5) instead of crashing or guessing.
- **Don't:** retrain at request time. Don't hardcode thresholds — pull constants from `config.py`.

### `backend/integrations/razorpay_client.py`
- **Do:** this is the *only* file that talks to Razorpay. Wrap `create_invoice`, `create_payment_link`, `fetch_invoice`/`fetch_payment` as small, clean functions using the official `razorpay` Python SDK (or direct REST if the SDK is missing a needed call). Test-mode keys only, read from config.
- **Don't:** scatter Razorpay calls into routers or engines. Don't hardcode key literals.

### `backend/clock.py` (new, small utility — see §6)
- **Do:** one function `now()` that returns real UTC time plus a stored virtual-day offset (a single row in a `demo_state` table, default 0). Every place in the codebase that currently calls `datetime.utcnow()` for business-logic decisions (escalation timing, stopping-rule windows) should call this instead.
- **Don't:** build a general time-travel framework. This is one function and one offset value, nothing more.

### `backend/routers/`
- **`invoices.py`** — `GET /invoices` (dashboard list: status, days overdue, reliability score, next scheduled action), `GET /invoices/{id}` (full ledger timeline + extracted promises), `POST /invoices/{id}/verify` (runs ledger integrity check)
- **`simulate.py`** — `POST /simulate/reply` (accepts an invoice id + raw reply text, runs promise extraction live, writes the ledger entry, returns the structured result)
- **`results.py`** — `GET /results` (batch run: recovered amount, precision/recall, exception list, side-by-side vs. the dumb baseline — see §7, this must match the track's stated bar exactly)
- **`demo.py`** (new) — `POST /demo/seed` (regenerate the synthetic dataset deterministically, same seed every time), `POST /demo/advance-clock` (`{"days": N}`, moves the virtual clock forward and re-runs the escalation scheduler pass so state updates immediately), `POST /demo/reset` (wipe + reseed, for repeatable takes)

### `backend/main.py`
- Wire up all routers + DB session dependency injection only. No decision logic here.

## 5. Rules carried over from the original design — do not relax these

- Escalation engine makes zero LLM calls, ever. This is what makes it defensible as provable, not "AI vibes."
- Promise extraction never falls back to regex, and never invents a number or date the customer didn't actually state. `has_commitment: false` / null amount / null date are valid, expected outputs.
- Ledger rows are never UPDATE'd or DELETE'd, enforced at the application layer.
- Reliability score is never hand-edited — always recomputed via the engine.
- Train/test split for the ML model is by customer, never by invoice (prevents leakage).
- Hard ceiling: max 6 automated contacts per invoice, independent of stage. 10-day observation window after the formal stage before `escalated_to_human_review`.

## 6. Demo mode — new requirement, this is the whole point

The problem with the original design for a *live* 5-minute video: due dates and promised dates are naturally days-to-weeks apart. Without a way to compress that, the only thing provable on camera is a pre-baked batch result, not the mechanism actually running.

**Fix:** the virtual clock (§4) plus a small, always-visible control bar in the frontend, gated behind `VITE_DEMO_MODE=true` so it's invisible in a "real" deployment:

- **Seed Data** — calls `POST /demo/seed`
- **Advance +1 Day** / **Advance +7 Days** — calls `POST /demo/advance-clock`, dashboard and invoice detail re-fetch and visibly update (stage changes, new ledger entries appear)
- **Reset Demo** — calls `POST /demo/reset`, for a clean repeatable take

This bar is a UI element in the existing layout — **not a fifth page.** Do not build anything more elaborate than this (no calendar picker, no per-invoice clock, no undo).

## 7. Frontend — four screens + the demo bar, nothing else

- **`/dashboard`** — invoice list: status, days overdue, reliability score, next scheduled action. Demo bar lives here (or in a shared layout header, either is fine).
- **`/invoice/:id`** — full ledger timeline, extracted promises, a "Verify Integrity" button that visibly passes — and, ideally, a way to show it fail (see demo script for how to stage this without building extra UI for it).
- **`/simulate`** — paste a customer reply, watch structured extraction happen live. This is the best single demo moment; do not under-build it.
- **`/results`** — batch run: recovered amount, precision/recall, the honest exception list, side-by-side against the dumb fixed-schedule baseline. This must visibly answer "isn't this just reminders?" — the comparison to baseline is not optional polish, it's the track's actual bar.

## 8. Known limitation — have the answer ready, don't build around it

The hash chain proves nothing was quietly edited *within* the chain — it does not protect against someone with full DB access regenerating the entire chain from scratch. If time allows (P2, only after everything else works): periodically commit the ledger's latest hash to the git repo itself as an independent, externally-timestamped record. If it doesn't get built, the honest spoken answer in the demo/pitch is enough — do not skip mentioning this limitation if asked live.

## 9. Build order

1. Read all existing files (§0) — do not skip this
2. `engines/reliability.py`
3. `integrations/razorpay_client.py`
4. `clock.py` + `demo_state` table + `routers/demo.py`
5. `routers/invoices.py`, `routers/simulate.py`, `routers/results.py`
6. Wire `main.py`
7. Frontend: Dashboard → InvoiceDetail → Simulate → Results → demo control bar last
8. Run `data/generate_synthetic.py` and `ml/train_reliability_model.py` if not already run against current code; run the batch evaluation; **record the actual numbers it produces** — never state a metric that hasn't come out of an actual run
9. Confirm the scripted vague-reply test case (see `00_PROJECT_BRIEF.md` context / original architecture notes) still produces `needs_review`, not a guessed number
10. Rehearse the full advance-clock → escalate → reply → extract → payment → reliability-update loop at least twice before recording anything
