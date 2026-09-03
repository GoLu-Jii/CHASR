# CHASR — AI Revenue Recovery for B2B

CHASR is a small-business invoice recovery agent for overdue B2B receivables.
It turns customer replies into structured promises, scores payment reliability,
chooses a deterministic recovery action, and records every step in a hash-chained
audit ledger.

## Demo flow

1. Start the API: `uvicorn backend.main:app --reload`
2. Start the frontend: `cd frontend; npm run dev`
3. Open the dashboard and run **Run midnight cron**.
4. Open an invoice, paste a customer reply, and show:
   - Gemini extracts amount, date, and confidence.
   - CHASR chooses the next action.
   - The ledger records and verifies the full chain.
5. Use the Mitra scenario to demonstrate safe human handoff for vague replies.

## Architecture

- FastAPI + SQLite + SQLAlchemy
- Gemini JSON-mode promise extraction
- Deterministic nudge → firm → formal escalation
- Explainable scikit-learn reliability model
- Razorpay test-mode invoice/payment-link integration
- Append-only SHA-256 audit ledger

WhatsApp/SMS delivery is simulated for the MVP; the exact outbound template is
shown and logged instead of sent to a real customer.

## Local setup

Copy `.env.example` to `.env`, add the available API keys, then install
`requirements.txt` in a virtual environment. The app still runs without Gemini
or Razorpay keys using safe demo fallbacks.