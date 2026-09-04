# CHASR — 5-Minute Demo Video Script

This is for you, not the code-writer AI. It's built around what the judges actually said they read for:

> Problem taste · Build quality · AI judgment · Failure recovery

...and Track 3's stated bar specifically:

> Show measured money recovered across a batch, with compliant escalation, stopping rules, and an audit trail.

Every beat below maps to at least one of those. Don't skip the mapping in your head while recording — it's why each shot is there.

## Before you hit record — checklist

- [ ] `.env` has real `GROQ_API_KEY`, `RAZORPAY_KEY_ID`, `RAZORPAY_KEY_SECRET` (test mode)
- [ ] Run `POST /demo/reset` once, right before recording, for a clean known state
- [ ] Have the Razorpay test-mode dashboard open in a second tab, ready to flip to
- [ ] Run the batch evaluation once beforehand and **write down the real numbers it produced** — never say a number on camera you haven't actually seen come out of a run
- [ ] Do one full silent rehearsal of every click, so you're not discovering UI lag live

## 0:00 – 0:35 — The problem (Problem taste)

Say the one-line problem plainly, don't over-narrate:

> "Once a B2B invoice goes overdue, it's either a human manually chasing every account, or a dumb script sending the same message on a schedule. Neither tracks what the customer actually promised, neither adjusts to who they are, and neither leaves an audit trail. That gap sits between issuing an invoice and the money landing — nobody's tool covers it."

Show: `/dashboard` with a handful of overdue invoices at different stages.

## 0:35 – 1:15 — Why this, why Razorpay

> "Razorpay's own Agent Studio page lists seven shipped agents — and separately names 'following up on unpaid invoices until they're paid' as something it hasn't built yet. Smart Collect only reconciles money that's already arrived. This runs before that, on Razorpay's real rails."

Show: open any invoice detail page, click **Create Razorpay test link**, and show the returned provider IDs and payment link in the Razorpay test-mode panel. The success message must say **Live Razorpay test object created**, not **Mock fallback**. Open the payment link in another tab if desired, then flip to the Razorpay test dashboard and search for the invoice ID or payment-link ID to prove it was created through the API.

## 1:15 – 2:15 — Live extraction (AI judgment)

This is the best individual moment — lead with it, don't rush it.

Go to `/simulate`. Paste in a live, unscripted-looking but representative reply, e.g. a partial commitment ("50% by Thursday, rest by month end"). Show the structured output appear: amount, date, confidence. Then do the harder one — paste the vague reply with no real numbers in it, and show extraction correctly returns `has_commitment: true`, `amount: null`, `confidence: vague` — **it doesn't invent a figure.**

> "The escalation ladder itself never calls an LLM — it's deterministic, template-based, fully provable. The one place AI runs is reading what a customer actually wrote — and it's built to admit when it doesn't know a number rather than guess one."

That line covers both AI judgment (right tool in the right place) and sets up the failure-recovery beat.

## 2:15 – 3:00 — Time compression + reliability-driven escalation (Build quality)

Click **Advance +7 Days** on the demo bar. Show an invoice move stage on the dashboard live, with the reliability score visibly influencing pace — a low-reliability customer escalating faster than a high-reliability one on the same days-overdue.

> "This isn't waiting on a cron job — the whole pipeline is running right now, compressed. In production the clock is real; for this demo I'm advancing it so you can see the mechanism, not just a snapshot."

## 3:00 – 3:40 — Audit ledger (Failure recovery / trust)

Open `/invoice/:id`, show the ledger timeline, click **Verify Integrity** — passes. If you built the tamper-check bonus (§8 of build spec), this is the moment to show a manually-edited row failing verification. If not built, say the limitation out loud instead of hiding it:

> "The hash chain proves nothing was quietly edited after the fact — it doesn't protect against someone with full database access rebuilding the whole chain. The real fix for that is committing the ledger's latest hash into git as an independent record outside the app."

Saying this unprompted is stronger than getting caught by it live.

## 3:40 – 4:30 — Batch results vs. baseline (the track's actual bar)

Go to `/results`. State the real numbers from your actual run — recovered amount, precision/recall, and the targeting comparison against the dumb fixed-schedule baseline.

> "On the same 50 invoices, CHASR recovered [observed amount] in the held-out batch, with [precision] precision and [recall] recall. The adaptive and fixed-schedule target sets are shown side by side; this dataset has no counterfactual payment outcomes, so we don't invent a recovery uplift — and here's the exception list it flagged honestly instead of hiding."

Fill in `[X]` only with what your own batch run actually produced.

## 4:30 – 5:00 — Positioning + close

> "This isn't claiming the mechanism is new — enterprise AR platforms already prove it works. What's missing is this, for the MSME selling to another MSME, on WhatsApp instead of email, in Hinglish, settling through UPI — on rails Razorpay's already half-built. Longer term, the reliability score only knows what this system has personally seen. The real next step is the same thing wholesalers already do informally — asking each other about a new customer's reputation — digitized across the platform."

End on the dashboard or the results screen, not a blank slide.

## Things to actively avoid on camera

- Don't say "zero overlap with Smart Collect" — say "adjacent, not the same thing."
- Don't say "nobody does AI voice collections" — say "HighRadius specifically doesn't."
- Don't state a metric you haven't personally watched come out of a terminal run.
- Don't claim any credential, prior internship, or background you don't actually have.
