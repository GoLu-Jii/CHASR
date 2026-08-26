# Global Alternative Approaches — Beyond Collections Software

Addendum to `02_MARKET_RESEARCH.md` · Razorpay AI Buildathon · Track 3

## The short version

Everywhere in the world, this problem gets solved one of two ways: **chase the debtor** (dunning/collections software — already covered) or **stop chasing and get paid now by someone else** (factoring — sell the unpaid invoice to a third party who takes on the risk). This note covers the second mechanism globally, plus one genuinely different, older, low-tech answer that's closer to what you were actually asking about. None of it changes what you build in two weeks. Two things in here do change how precisely you can describe *who this is for*, and it's worth reading for that alone.

## 1. TReDS — India's own answer, and it sharpens your pitch

RBI-regulated, launched 2014, "without recourse" — an MSME uploads an invoice, multiple financiers bid to buy it at a discount, the MSME gets cash immediately, and the financier (not the MSME) now owns the risk of chasing the buyer. This is a real, mature, government-backed solution to almost exactly your problem statement — cash trapped in receivables, MSME working capital strain.

**Why it doesn't compete with you, and why that matters:** TReDS only works when the *buyer* is a large, TReDS-registered corporate or government/PSU entity that logs in and formally accepts the invoice on the platform. It's built for MSME-sells-to-large-corporate. It has nothing for MSME-sells-to-another-MSME — which, realistically, is a huge share of real B2B trade in India, and exactly the case your problem statement describes (a founder or ops person chasing "whoever emailed last"). **This is worth stating directly in your pitch**: TReDS already solved the MSME-to-large-corporate case by transferring the risk away entirely; nothing solves the MSME-to-MSME case, where there's no big buyer to lean on and no financier willing to underwrite it. That's a sharper, more specific "who this is for" than what's in `01_PROBLEM_STATEMENT.md` right now.

## 2. Reverse factoring / supply chain finance — same idea, seen globally

Africa's fintech wave (mobile money, Nigeria's OPay/Moniepoint, Kenya's M-Pesa business rails) mostly attacks a different layer — digitizing *payment*, not chasing overdue ones — and where it does touch receivables, it's the same reverse-factoring mechanism as TReDS: a creditworthy buyer's credit rating gets extended down to their supplier. Same conclusion as above — different mechanism (sell the risk, don't chase it), same "doesn't cover SME-to-SME" gap.

## 3. Blockchain / DeFi invoice tokenization — same mechanism, newer rails

A real, active global trend — invoices minted as tokens, sold to decentralized liquidity pools instead of one bank, instant stablecoin settlement (PayPal and TCS Blockchain are doing this for real with freight invoices right now, nearly $1B in annual flow). Interesting to know exists. **Not a fit here** — it's still factoring, same "who's covered" gap as TReDS, and crypto/stablecoin rails bring real regulatory friction in India that has nothing to do with your actual problem. Mention it if asked "have you looked at blockchain approaches" so you're not caught flat-footed — don't build toward it.

## 4. The actual "small village" answer — and it's a real idea, just not for the MVP

This is the one worth reading twice. There's a real term for it: **"church steeple lending"** — historically, credit was extended within the radius where you could see the local church steeple, because everyone in that radius personally knew everyone else's reputation. There's also solid research on live informal credit markets today: shopkeepers extending credit to regular customers based on reputation, and — this is the important part — **wholesalers routinely asking *other* wholesalers about a new retailer's reputation before extending credit themselves**, not relying only on their own transaction history with that person.

That second finding directly names a real weak spot in your own design: your reliability score only knows what *your* system has personally seen. A brand-new customer starts with zero signal, same problem a village shopkeeper has with a stranger — except the shopkeeper's real-world solution is to ask a neighboring shopkeeper what they know. Software doesn't have to reinvent that; it can literally digitize it.

**The real idea, correctly scoped as vision, not MVP:** eventually, anonymized reliability signals could be pooled across multiple businesses using the same platform — so a brand-new customer isn't a total unknown if they've already got a track record with someone else on the network. That's "church steeple lending," just digitized and no longer limited by geography. It's a genuinely good line for the "future scope" section of your pitch — a believable next step that a panelist would recognize as a real, non-obvious extension, not filler. It is **not** buildable in two weeks (needs real participating businesses and a data-sharing/consent model), so don't attempt it now — just name it as where this goes next.

## Bottom line

Nothing here replaces the four-engine build. What it gives you: a sharper, more specific "who this is for" (MSME-to-MSME, the one case TReDS and reverse factoring both structurally can't reach), confidence that you're not missing an obviously-better existing solution, and one genuinely good, well-grounded vision line for your pitch's closing instead of a generic "and in the future we'll add more features."
