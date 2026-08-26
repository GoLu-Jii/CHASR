# B2B Invoice Recovery Agent — Problem Statement & Solution

**Razorpay AI Buildathon · Track 3, AI Revenue Recovery**

## The problem, in one line

B2B businesses selling on net-30/60/90 terms lose working capital and rack up bad debt because once an invoice goes overdue, recovery relies on reactive, unstructured, manual follow-up that doesn't scale, doesn't track what customers actually promised, and often damages the relationship in the process.

## Core problem statement

There's an operational void between an invoice being issued and the money actually landing. Payment gateways give merchants tools to *generate* invoices and *reconcile* money once it arrives — nothing helps when a client simply doesn't pay on time. That gap is filled today by either a human manually chasing every account, or a dumb cron job blasting the same message on a fixed schedule. Neither scales, and neither is auditable.

## Who this affects

B2B businesses, SaaS providers, wholesalers, and MSMEs selling on net-30/60/90 terms. Realistically, at the size that would actually adopt something like this, there's no dedicated collections department — it's a founder or ops person squeezing this in between everything else, chasing whoever emailed last or whoever owes the biggest number. That's exactly why it stays reactive and unstructured today.

## The four structural breakdowns

**1. The "dumb reminder" vs. "manual overhead" trade-off**
Automated tools send the same generic template on a fixed schedule — easily ignored, and it treats a reliable long-term client the same as a habitual defaulter. Manual chasing doesn't scale past a handful of accounts and delays intervention on smaller invoices.

**2. The promise-to-pay tracking void**
Debtors rarely reply "yes" or "no." They reply with conditional, partial commitments — *"we're waiting on client disbursement, will clear 50% by Thursday and the rest by month-end."* These live in scattered email threads and WhatsApp chats. Finance teams lose track of promised dates, miss broken promises, or send an aggressive reminder to someone who already agreed on a date.

**3. Lack of dynamic risk and behavioral context**
Escalation doesn't adjust based on who the customer actually is — a historically punctual buyer facing a one-off cash crunch gets treated the same as a repeat, deliberate late-payer. There's no system to decide when to nudge politely, when to offer a split-payment link, when to get firm, and when to stop and hand off to a human.

**4. No auditable recovery trail**
In a small team, a sales rep might informally extend a deadline while accounts sends a formal demand notice the same week. There's no single, tamper-evident record of every status change, message, and promise — weakening both internal coordination and legal standing if a dispute ever escalates.

## Measurable business impact

- **Inflated DSO and cash flow strain** — capital sits trapped in unpaid receivables instead of being reinvested, often forcing reliance on expensive short-term credit
- **Bad debt slippage** — recovery odds drop sharply once an invoice passes 60–90 days overdue; the later the intervention, the more of that money is written off for good
- **High collection ops cost** — hours burned drafting reminders, logging replies, and cross-checking bank records by hand instead of on higher-leverage work

## The derived solution

One agent, four engines, each fixing exactly one of the breakdowns above:

| Engine | Fixes | What it does |
|---|---|---|
| **Escalation engine** | #1 | A risk-tiered ladder (nudge → firm → formal), not a cron job — pace and tone depend on the specific customer, delivered through pre-approved templates, never freely generated text |
| **Promise extraction** | #2 | Reads the actual reply and pulls a structured commitment — amount, date, how firm it sounds — instead of a human trying to remember what someone said in a WhatsApp thread |
| **Reliability score** | #3 | Built from that customer's own promise-keeping history; decides both how much patience they get and what kind of intervention fits |
| **Audit ledger** | #4 | A hash-chained, append-only record of every status change, message, and promise — one shared source of truth across the team, not just evidence for a future dispute |

## Who it's for

The founder or ops person doing collections at a small B2B business — not a dedicated finance department. It's for the business that's currently guessing who to chase today, based on who emailed last or who owes the most, instead of who's actually at risk.

## Why this, why now, why Razorpay

Razorpay's own Agent Studio page lists *"following up on unpaid invoices until they're paid"* under a section called "here's what others are automating" — explicitly separate from the seven agents it has actually shipped. Razorpay's own Smart Collect 2.0 only reconciles money that has *already arrived*; it does nothing before that. This agent is built to run on Razorpay's real rails — the Invoices API and Payment Links, through the official MCP server — so it's not a disconnected concept, it's the missing half of something Razorpay has already partly built and publicly wants filled.

## What this is, and isn't, claiming

This is **not** a claim that the underlying mechanism is novel — a mature, well-funded global industry (AR automation / collections software) already does versions of this for large enterprises, with published results. See `02_MARKET_RESEARCH.md` for the full picture.

What's actually being claimed: a specific, validated, still-empty intersection — built for the Indian SME that can't afford or qualify for an enterprise AR platform, communicating over WhatsApp instead of email, in Hinglish instead of English-only, settling through UPI/Razorpay instead of ACH or wire transfer.
