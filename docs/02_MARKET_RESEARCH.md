# Market Research — B2B Invoice Recovery Agent

**Razorpay AI Buildathon · Track 3, AI Revenue Recovery**

## Positioning in one sentence

Don't claim the mechanism is new — claim it's *proven* elsewhere, and point at the specific, verified intersection nobody has built: SME-sized, WhatsApp-native, Hinglish-capable, UPI-settled.

## 1. The existing global category: AR automation / collections software

This is a mature, named industry — "accounts receivable automation," part of the broader "order-to-cash" (O2C) software category. Real players, real revenue, real published outcomes. If a pitch claims "nobody has built this," that's an instantly checkable overclaim — the honest framing is "an entire category proves this works, just not for who actually needs it here."

### HighRadius (category leader)

- Runs 15+ orchestrated AI agents across the O2C workflow under an "Agentic AI" / "Autonomous Receivables" brand
- Published outcomes (verified against HighRadius's own materials, though the exact figure varies by report — **always cite the specific report if quoting a number, don't state one bare**): roughly 10–30% DSO reduction, up to ~20% reduction in past-due balances within six months, and AR-team productivity gains cited as 30% in one HighRadius page and 40% in another
- Built for large enterprises: SAP / Oracle / NetSuite / Microsoft Dynamics integrations, "contact us" pricing, typical implementation time of 3–6 months
- Outreach channels are email, portal reminders, and human-placed calls — **not WhatsApp**
- **Confirmed gap, verified against an independent third-party review, not just HighRadius's own claims**: HighRadius does not conduct AI voice conversations. It is explicitly described as "analytical and workflow-oriented, not conversational." It does not negotiate settlement terms in real time or place calls to debtors.
- Not built for the SME end of the market, and not built for consumer debt (different regulatory regime — FDCPA/TCPA/Reg F in the US, not relevant here anyway since this is a B2B play)

### AgentCollect (important correction — voice AI isn't fully unclaimed globally)

A separate company that exists specifically to bolt AI voice calling onto HighRadius, filling the exact gap named above. This means: voice-based AI collection **does** exist in the market generally — it's unclaimed *by HighRadius itself*, not unclaimed as a category. This doesn't hurt this project (the current MVP doesn't use voice), but don't overstate the gap as "nobody anywhere does AI voice collections" — say precisely "HighRadius doesn't," which is the claim that's actually been verified.

### Chaser, Tesorio, Gaviti, Upflow

Same general category — automated dunning, promise-to-pay tracking (a real, industry-standard term), risk-based escalation. Same pattern as HighRadius: enterprise/SMB-Western-market first, integrate with Xero/QuickBooks/SAP, none touch UPI or India-specific SME workflows.

## 2. The Razorpay-specific landscape

### What Razorpay has already shipped — Agent Studio (confirmed live)

Seven named, production agents currently listed on Razorpay's own Agent Studio page:

1. **Dispute Responder** — auto-responds to chargebacks with evidence
2. **Subscription Recovery** — retries and nudges on failed subscription payments
3. **Abandoned Cart Conversion** — re-engages customers after checkout drop-off
4. **RTO Shield** — flags high-risk cash-on-delivery orders before dispatch
5. **RTO Insights** — analyzes return-to-origin patterns by pincode/product/customer
6. **Settlement Insights** — daily settlement summary via WhatsApp
7. **Cashflow Forecaster** — predicts cash position 3–7 days ahead

*(Note: some earlier press coverage cited "eight" agents — that came from double-counting Abandoned Cart's two launch partners as separate agents. Seven is the current, accurate count.)*

### The gap, stated in Razorpay's own words

On the same live page, in a section titled **"Here's what others are automating"** — deliberately separate from the seven named/shipped cards above — the first line is: *"Following up on unpaid invoices until they're paid."* This is Razorpay acknowledging real demand for exactly this, while conspicuously not giving it a name, a card, or a "production-ready" label the way it did the other seven.

### Smart Collect 2.0 — the near-miss, framed correctly

A real, live RazorpayX product. Gives merchants unique virtual account identifiers per customer so any incoming NEFT/RTGS/IMPS/UPI transfer auto-matches to the right customer/invoice. **It is purely reactive** — it only handles money that has already arrived. Nothing in it sends a reminder, negotiates a date, or tracks whether a customer kept their word.

**Correct claim: "adjacent to Smart Collect, not the same thing, and not zero overlap."** Overclaiming "zero overlap" is the one mistake that would look bad in front of a panelist familiar with the product.

### Razorpay Invoices API (confirmed real, and richer than initially assumed)

Full CRUD — create, issue, update, cancel, duplicate, search. GST-compliant invoicing (via dashboard). Embedded payment link sent automatically. Native due-date/expiry handling. Native partial-payment tracking (`amount_paid` / `amount_due` fields). Built-in SMS/email notifications. Webhooks including `invoice.paid` and `invoice.expired`. This should be used directly as the real invoice object in the build, not reinvented as a purely internal table.

### Razorpay MCP server (confirmed real)

Open-source, MIT-licensed, hosted at `mcp.razorpay.com` — zero local setup via `npx`. The hosted/remote version deliberately restricts some tools (refunds, settlements); full access to those needs the self-hosted Docker version. Not a blocker for this project, since the core need is Payment Links and Invoices, not refunds.

## 3. Regulatory landscape — why live messaging is simulated, not real

### TRAI DLT (SMS, India)

Mandatory for any business sending bulk/commercial SMS. Three phases: entity (Principal Entity) registration → sender ID/header registration → content template registration. Entity registration typically takes 1–3 working days; template approval typically 3–7 working days once registered — **not "weeks,"** contrary to an earlier draft of this doc. Requires real business KYC (PAN, GST, business registration documents) before you can even begin.

### WhatsApp Business API (Meta)

Template approval itself is fast — usually minutes to 24–48 hours. The real bottleneck is Business Manager verification, which requires actual legal business documents and can add several working days on top.

### The honest reason to simulate messaging (this is the framing to use)

Not "the approval takes too long for a hackathon" — the real, harder-to-argue-with reason is: **both processes require you to already be a verified, registered business entity**, which a student building a hackathon prototype fundamentally is not. Simulate the sends, log exactly what template would have gone out, and say this plainly rather than hiding it.

## 4. Adjacent proof points worth citing

**WhatsApp-based collections, different domain.** Indian fintechs running WhatsApp-based, local-language collections for consumer loan EMI recovery report 25–35% improvement in on-time recovery. Different domain (consumer lending, not B2B trade receivables) — but real evidence that the channel and tone work in an Indian context.

**Trade credit insurance — not a competitor.** A separate, ~$20B global market (Allianz Trade, Coface, Atradius) that solves an adjacent problem completely differently: businesses pay a premium and get insured against non-payment, instead of chasing the money. Different mechanism, different customers (large exporters, not domestic SMEs). Worth knowing it exists; not something this project competes with.

## 5. Bottom-line pitch positioning

> "This category works, at scale, with measured results elsewhere — the mechanism isn't a risk, it's proven. What's actually missing is a specific intersection: built for the SME that can't afford or qualify for an enterprise AR platform, running on WhatsApp instead of email, speaking Hinglish instead of English-only, and settling through UPI instead of ACH — on rails Razorpay has already half-built and publicly wants filled."
