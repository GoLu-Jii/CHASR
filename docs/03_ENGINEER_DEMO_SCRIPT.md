# CHASR — Engineer-Audience Demo Script (Verified)

This script matches the current implementation and synthetic database. Reset the demo once and restart the backend before recording.

Hi, I’m Gaurav. This is CHASR: a B2B invoice-recovery workflow for the period after an invoice becomes overdue.

The problem is simple. Small businesses either chase customers manually, which does not scale, or use a fixed reminder schedule, which treats a reliable customer and a repeatedly broken promise exactly the same. CHASR adds a bounded, auditable decision process in between.

There are four components, all connected through one internal append-only ledger.

First is escalation. It is deliberately not an LLM. It is a deterministic ladder: nudge, firm, then formal. The inputs are invoice age, customer reliability, pending commitments, and stopping rules. A low-reliability customer moves sooner; a high-reliability customer gets more time.

[On Collections, point to Maple Ridge Foods and Harborline Freight after Reset. Both start at 13 days overdue and at the nudge stage. Click Advance +7 days. Maple Ridge, the higher-reliability customer, stays at nudge at 20 days; Harborline, the low-reliability customer, moves to firm.]

That is the useful distinction: the invoice age is the same, but the action is different because the history is different. There are two safety limits: no more than six automated contacts for an invoice, and a formal invoice with no response for ten days is handed to human review rather than contacted forever.

Second is promise extraction. This is the only LLM call. The configured model is openai/gpt-oss-20b through Groq, with temperature zero. I ask it for a narrow JSON contract, then the application validates the returned values before creating a promise: amounts must be positive and cannot exceed the invoice; dates must parse; and confidence must be firm, soft, or vague. There is no regex fallback.

[Go to Customer reply. Select Harborline Freight, invoice amount ₹2,10,000. Paste: “We can release 50% next Wednesday and the balance after our customer settles.” Click Extract commitment.]

The first tranche should be ₹1,05,000 with a resolved date. The remaining tranche has no concrete date, so it requires review rather than getting an invented deadline.

[For the ambiguity case, use a fresh invoice and paste: “We will try to pay something soon.”]

The important behaviour is that CHASR does not fabricate an amount or date. Depending on the model’s structured response it records either a vague commitment with null fields and routes it to review, or no clear commitment. Both are safe outcomes. Do not claim a specific model output unless it is visible on screen.

The virtual clock makes deadline behaviour demonstrable. A commitment date is evidence; it is never rewritten. Once the virtual day passes its stated date, the next scheduler pass marks it broken, writes a promise-status event to the ledger, and escalates — severity is still reliability-aware: a historically risky customer goes straight to formal, while a customer who usually keeps promises gets one firm chance before formal. This preserves the same reliability gradient even after a promise is broken. Repeating the exact same reply later cannot reinterpret “next Wednesday” and silently move the original date.

Third is reliability scoring. It is a scaled, class-balanced scikit-learn logistic-regression model. The model uses only promise history: kept-full, kept-partial, broken, rates, and lateness. Runtime responsiveness is a small bounded calibration. A customer without promise history gets the documented neutral score of 0.50.

The train/test split is by customer, not invoice, so one customer’s other promises cannot leak into the held-out evaluation. On the current dataset, there are 993 customers with promise history and 11,588 promise rows. The split is 695 training customers and 298 held-out customers. The current held-out result is precision 0.807, recall 0.611, and ROC-AUC 0.721. This is synthetic-data validation of the pipeline, not a production-performance claim.

Fourth is the audit ledger.

[Open any invoice, scroll to Audit timeline, and click Verify ledger.]

Each ledger entry includes the hash of the previous entry for that invoice. Verify ledger recomputes that chain live. It detects a quiet modification to a row in the chain. It does not protect against an administrator with complete database access rewriting the entire chain and recomputing every hash. An external checkpoint is the next hardening step; it is not implemented today.

[Open Performance.]

These are the actual current result-screen numbers: 50 held-out invoices in the displayed batch, ₹53,53,248 observed recovered, precision 0.807, recall 0.611, and eight displayed broken-promise exceptions. The adaptive and fixed-schedule groups are target lists. They show different targeting choices. CHASR deliberately reports zero recovery uplift because historical data does not tell us the counterfactual result of sending a different reminder policy. Claiming an uplift here would be made up.

Finally, Razorpay is integrated as a test-mode payment rail. CHASR keeps its own SQLite invoice and ledger records as workflow truth, and can create a Razorpay test invoice/payment link from an invoice-detail page and sync a provider payment status. Call it “live” only after the UI shows a non-mocked provider ID and link. If credentials or network access fail, the UI honestly shows the provider error or mock fallback.

That is CHASR: narrow use of an LLM for language interpretation, deterministic financial policy for escalation, an interpretable reliability score, and an auditable record of every decision.

## Recording sequence

1. Restart backend; use Reset once.
2. Show Collections and the two matched-age invoices.
3. Show Customer reply with the clear partial commitment.
4. Show the vague-reply safety case on a different invoice.
5. Return to Collections and use +7 days for the stage comparison.
6. Open an invoice, show a broken commitment if applicable, then verify ledger.
7. Open Performance and read only the figures above.
8. Create a Razorpay link only if your test credentials and network are working.
