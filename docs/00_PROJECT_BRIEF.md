# CHASR — Project Brief

**Razorpay AI Buildathon · Track 3: AI Revenue Recovery**

> Give this file to your code-writer AI first, as context. Give `01_BUILD_SPEC.md` next, as the actual work order. `02_DEMO_SCRIPT.md` is for you, for recording the pitch video — not for the code-writer.

## What CHASR is

A B2B invoice recovery agent. When an invoice goes overdue, CHASR decides *when* to escalate, *how firmly*, extracts what the customer actually promised from their reply, scores whether that customer tends to keep promises, and proves the whole thing worked on a batch — with a tamper-evident record of every step.

## The problem, in one line

Once a B2B invoice goes overdue, recovery today is either a human manually chasing every account (doesn't scale) or a dumb cron job blasting the same message on a fixed schedule (easily ignored, treats every customer the same). Neither tracks what a customer actually promised, neither adjusts to who the customer is, and neither is auditable.

## Who it's for

The founder or ops person doing collections at a small B2B business — not a dedicated finance department. More specifically: **MSME selling to another MSME.** India's TReDS platform already solves invoice-financing for MSME-to-large-corporate (a big buyer formally accepts the invoice, a financier takes on the risk). Nothing solves the MSME-to-MSME case, where there's no big buyer to lean on and no financier willing to underwrite it — that's exactly the gap this fills.

## The solution: four engines, one ledger

| Engine | Fixes | What it does |
|---|---|---|
| **Escalation engine** | Generic reminders vs. manual overhead | Deterministic ladder (nudge → firm → formal), zero LLM calls, picks from pre-approved templates based on days overdue + reliability score |
| **Promise extraction** | Lost/misremembered commitments | The only place an LLM runs. Reads a customer's reply, pulls a structured commitment (amount, date, confidence) — or honestly returns "no clear commitment" instead of guessing |
| **Reliability scoring** | Treating every customer the same | Classic ML (logistic regression) trained on each customer's own promise-keeping history. One number: probability they follow through |
| **Audit ledger** | No record of what happened when | Append-only, hash-chained log of every status change, message, and promise. The single source of truth everything else reads from |

## What's real, what's simulated — say this on camera, don't hide it

- **Real:** Razorpay Invoice + Payment Link creation (test mode, via API/MCP), the ledger hash chain, the reliability model trained and evaluated on synthetic data, the LLM extraction call.
- **Simulated, stated plainly:** actual WhatsApp/SMS delivery. Both TRAI DLT and WhatsApp Business API verification require a registered business entity to even begin — a student building a hackathon prototype doesn't have one. CHASR logs exactly what message would have gone out, on the correct channel, at the correct time.

## Why Razorpay, why now

Razorpay's own Agent Studio page lists seven shipped agents — and separately, under "here's what others are automating," names "following up on unpaid invoices until they're paid" without giving it a card. That's a public, named gap. Razorpay's Smart Collect 2.0 is adjacent but doesn't compete with this: it only reconciles money that has *already arrived* — it sends no reminder, tracks no promise, makes no decision. CHASR runs on Razorpay's real rails (Invoices API + Payment Links) to fill the part of the loop Razorpay hasn't built yet.

## What this is NOT claiming

The underlying mechanism (dunning, promise-to-pay tracking, risk-based escalation) is proven at enterprise scale by HighRadius and others — this isn't a claim of a new category. The actual claim: a specific, still-empty intersection — built for the SME that can't afford or qualify for an enterprise AR platform, on WhatsApp instead of email, in Hinglish instead of English-only, settling via UPI instead of ACH.

Don't say "zero overlap with Smart Collect" — say "adjacent, not the same thing." Don't say "nobody does AI voice collections" — say "HighRadius specifically doesn't" (a separate company, AgentCollect, already bolts voice onto it).

## One line for the close of the pitch (vision, not MVP)

The reliability score only knows what CHASR has personally seen — a brand-new customer starts as a total unknown, the same problem a village shopkeeper has with a stranger. The real-world fix for that is centuries old: wholesalers ask *other* wholesalers about a new retailer's reputation before extending credit — "church steeple lending." The believable next step for this system is the same idea digitized: anonymized reliability signals pooled across businesses on the platform, so a new customer isn't a blank slate if they already have a track record elsewhere. Not buildable in two weeks — name it as where this goes next, don't attempt it.
