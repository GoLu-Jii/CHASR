# backend/engines/escalation.py

from datetime import timedelta
from sqlalchemy.orm import Session

from backend.clock import now
from backend.models import (
    Invoice, InvoiceStatus, EscalationStage,
    Promise, PromiseStatus, Ledger, LedgerEventType,
)
from backend.engines import ledger as ledger_engine
from backend.engines import reliability
from backend.integrations import razorpay_client
from backend import config

TEMPLATES = {
    EscalationStage.nudge: "Hi {name}, friendly reminder that invoice {inv_id} for {amount} was due on {date}. Could you let us know when it might be cleared?",
    EscalationStage.firm: "Hi {name}, invoice {inv_id} for {amount} is now significantly overdue. Please process this payment immediately via this link: {link}",
    EscalationStage.formal: "ATTENTION: Invoice {inv_id} is severely overdue. Please pay immediately using {link}, or contact us today to agree a resolution. This account is being flagged for human review.",
}

_TERMINAL_STATUSES = {InvoiceStatus.paid, InvoiceStatus.written_off, InvoiceStatus.escalation_exhausted}

_STAGE_SEVERITY = {
    EscalationStage.none: 0,
    EscalationStage.nudge: 1,
    EscalationStage.firm: 2,
    EscalationStage.formal: 3,
}


def _reliability_band_stage(days_overdue: int, score: float) -> EscalationStage:
    """Reliability-adjusted escalation stage by days overdue.

    Reliability changes when a customer reaches firm/formal, while the stages
    themselves stay fixed. Low-reliability accounts are contacted sooner;
    high-reliability accounts earn more patience.
    """
    firm_after = config.FIRM_AFTER_DAYS
    formal_after = config.FORMAL_AFTER_DAYS
    if score <= config.LOW_RELIABILITY_THRESHOLD:
        firm_after = config.LOW_RELIABILITY_FIRM_AFTER_DAYS
        formal_after = config.LOW_RELIABILITY_FORMAL_AFTER_DAYS
    elif score >= config.HIGH_RELIABILITY_THRESHOLD:
        firm_after = config.HIGH_RELIABILITY_FIRM_AFTER_DAYS
        formal_after = config.HIGH_RELIABILITY_FORMAL_AFTER_DAYS
    if days_overdue > formal_after:
        return EscalationStage.formal
    if days_overdue > firm_after:
        return EscalationStage.firm
    return EscalationStage.nudge


def evaluate_and_escalate(session: Session, invoice_id: int):
    invoice = session.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.status.in_([InvoiceStatus.unpaid, InvoiceStatus.partially_paid]),
    ).first()

    if not invoice or invoice.status in _TERMINAL_STATUSES:
        return

    # The contact ceiling applies even when a promise has expired.  Otherwise a
    # broken promise could bypass the stopping rule and repeatedly send formal
    # notices whenever the scheduler runs.
    contact_count = (
        session.query(Ledger)
        .filter(Ledger.invoice_id == invoice_id, Ledger.event_type == LedgerEventType.escalation_sent)
        .count()
    )

    pending_promises = (
        session.query(Promise)
        .filter(Promise.invoice_id == invoice_id, Promise.status == PromiseStatus.pending)
        .order_by(Promise.promised_date.asc())
        .all()
    )

    if pending_promises:
        expired_promises = []
        has_incomplete_promise = False
        for promise in pending_promises:
            if promise.promised_date is None:
                has_incomplete_promise = True
                continue
            if promise.promised_date + timedelta(days=config.KEPT_GRACE_DAYS) < now():
                expired_promises.append(promise)

        if expired_promises:
            for promise in expired_promises:
                promise.status = PromiseStatus.broken
            session.commit()
            for promise in expired_promises:
                ledger_engine.append_entry(
                    session,
                    invoice.id,
                    LedgerEventType.promise_status_updated,
                    {
                        "promise_id": promise.id,
                        "status": PromiseStatus.broken.value,
                        "promised_date": promise.promised_date.isoformat(),
                        "reason": "Promise date passed without a recorded payment.",
                    },
                )
            if contact_count >= config.MAX_AUTOMATED_CONTACTS:
                _exhaust(session, invoice, reason=f"Hit the {config.MAX_AUTOMATED_CONTACTS}-contact ceiling after a broken promise.")
                return
            # A broken promise is severe, but reliability still modulates the
            # response: a customer who has historically kept promises gets one
            # firm chance before formal escalation, while a risky customer is
            # escalated formally immediately.
            score = reliability.score_customer(invoice.customer_id, session, persist=True)
            broken_stage = (
                EscalationStage.formal
                if score <= config.LOW_RELIABILITY_THRESHOLD
                else EscalationStage.firm
            )
            _execute_escalation(
                session, invoice, broken_stage, score,
                reason="Broken payment commitment after the promised date passed.",
            )
            return

        if has_incomplete_promise or invoice.needs_review:
            invoice.needs_review = True
            session.commit()
            return

        return  # STOPPING RULE 2 - all commitments remain inside grace

    days_overdue = (now() - invoice.due_date).days
    if days_overdue <= config.NUDGE_AFTER_DAYS:
        return

    if contact_count >= config.MAX_AUTOMATED_CONTACTS:
        _exhaust(session, invoice, reason=f"Hit the {config.MAX_AUTOMATED_CONTACTS}-contact ceiling.")
        return

    if invoice.current_stage == EscalationStage.formal and invoice.last_contacted_at:
        silence_days = (now() - invoice.last_contacted_at).days
        if silence_days >= config.OBSERVATION_WINDOW_DAYS:
            _exhaust(session, invoice, reason=f"No response {silence_days} days after formal notice.")
        return  # inside or past the window — either way, don't re-send formal on repeat

    score = reliability.score_customer(invoice.customer_id, session, persist=True)

    target_stage = _reliability_band_stage(days_overdue, score)
    has_broken_promise = session.query(Promise).filter(
        Promise.invoice_id == invoice_id,
        Promise.status == PromiseStatus.broken,
    ).first() is not None
    if has_broken_promise:
        target_stage = (
            EscalationStage.formal
            if score <= config.LOW_RELIABILITY_THRESHOLD
            else EscalationStage.firm
        )

    if _STAGE_SEVERITY[target_stage] < _STAGE_SEVERITY[invoice.current_stage]:
        target_stage = invoice.current_stage

    if target_stage == invoice.current_stage:
        if not invoice.last_contacted_at or (now() - invoice.last_contacted_at).days < config.RECONTACT_INTERVAL_DAYS:
            return

    reason = "Reliability-adjusted escalation schedule." if not has_broken_promise else "Broken payment commitment."
    _execute_escalation(session, invoice, target_stage, score, reason=reason)


def _exhaust(session: Session, invoice: Invoice, reason: str):
    invoice.status = InvoiceStatus.escalation_exhausted
    session.commit()
    ledger_engine.append_entry(session, invoice.id, LedgerEventType.escalated_to_human_review, {"reason": reason})


def _execute_escalation(session: Session, invoice: Invoice, stage: EscalationStage, score: float | None = None, reason: str | None = None):
    customer = invoice.customer
    payment_link = _ensure_payment_link(session, invoice)
    payment_url = payment_link.get("short_url") or f"https://rzp.io/test_{invoice.id}"

    message = TEMPLATES[stage].format(
        name=customer.name, inv_id=invoice.id, amount=invoice.amount,
        date=invoice.due_date.strftime("%d %b %Y"), link=payment_url,
    )

    invoice.current_stage = stage
    invoice.last_contacted_at = now()
    invoice.contact_count = (invoice.contact_count or 0) + 1
    session.commit()

    payload = {
        "stage": stage.value,
        "message_sent": message,
        "channel": "WhatsApp (Simulated)",
        "payment_link": payment_url,
        "reliability_score": score,
    }
    if reason:
        payload["reason"] = reason
    ledger_engine.append_entry(
        session=session, invoice_id=invoice.id, event_type=LedgerEventType.escalation_sent,
        payload=payload,
    )


def _format_message(invoice: Invoice, stage: EscalationStage, link: str | None = None) -> str:
    return TEMPLATES[stage].format(
        name=invoice.customer.name if invoice.customer else "Customer",
        inv_id=invoice.id,
        amount=invoice.amount,
        date=invoice.due_date.strftime("%d %b %Y"),
        link=link or f"https://rzp.io/test_{invoice.id}",
    )


def next_action(session: Session, invoice: Invoice) -> dict:
    """Read-only preview of what the scheduler would do next.

    Mirrors evaluate_and_escalate's precedence *exactly* so the UI can never
    drift from real policy. An expired dated commitment is surfaced first and
    is never masked by a companion incomplete commitment.
    """
    current_stage = invoice.current_stage.value if invoice.current_stage else "none"

    # written_off / paid -> done; escalation_exhausted -> handed to a human.
    if invoice.status in {InvoiceStatus.paid, InvoiceStatus.written_off}:
        return {"action": "No automated action", "stage": current_stage, "message": None, "nature": "no_action"}
    if invoice.status == InvoiceStatus.escalation_exhausted:
        return {"action": "Handed to human review", "stage": "formal", "message": None, "nature": "no_action"}

    contact_count = (
        session.query(Ledger)
        .filter(Ledger.invoice_id == invoice.id, Ledger.event_type == LedgerEventType.escalation_sent)
        .count()
    )
    pending_promises = [
        p for p in (invoice.promises or [])
        if p.status == PromiseStatus.pending
    ]
    now_ts = now()

    if pending_promises:
        # 1. An expired dated promise is marked broken and escalated this pass.
        expired = [
            p for p in pending_promises
            if p.promised_date and p.promised_date + timedelta(days=config.KEPT_GRACE_DAYS) < now_ts
        ]
        if expired:
            score = reliability.score_customer(invoice.customer_id, session, persist=False)
            broken_stage = EscalationStage.formal if score <= config.LOW_RELIABILITY_THRESHOLD else EscalationStage.firm
            if contact_count >= config.MAX_AUTOMATED_CONTACTS:
                return {"action": "Handed to human review (contact ceiling)", "stage": broken_stage.value, "message": None, "nature": "exhaust"}
            return {
                "action": "Mark broken and send notice",
                "stage": broken_stage.value,
                "message": "The payment commitment has expired. CHASR will mark it broken and send a "
                           f"{broken_stage.value} notice.",
                "nature": "broken_send",
            }
        # 2. An incomplete (no-date) commitment pauses automation for a human.
        #    The engine honours needs_review only inside the pending branch.
        if invoice.needs_review or any(p.promised_date is None for p in pending_promises):
            return {"action": "Human review required", "stage": current_stage, "message": None, "nature": "human_review"}
        # 3. STOPPING RULE 2: all commitments within grace -> no send, only a wait.
        first = pending_promises[0]
        if first.amount is not None and first.promised_date:
            return {
                "action": "Wait for promised payment date",
                "stage": current_stage,
                "message": "Automation paused until "
                           f"{first.promised_date.strftime('%d %b %Y')}. CHASR will evaluate payment against this promise.",
                "nature": "wait_promise",
            }
        return {"action": "Human review required", "stage": current_stage, "message": None, "nature": "human_review"}

    # 4. No pending commitments: follow the reliability-adjusted overdue ladder.
    days_overdue = (now_ts - invoice.due_date).days
    if days_overdue <= config.NUDGE_AFTER_DAYS:
        return {"action": "No automated action", "stage": current_stage, "message": None, "nature": "schedule_return"}

    if contact_count >= config.MAX_AUTOMATED_CONTACTS:
        return {"action": "Handed to human review (contact ceiling)", "stage": current_stage, "message": None, "nature": "exhaust"}

    if invoice.current_stage == EscalationStage.formal and invoice.last_contacted_at:
        if (now_ts - invoice.last_contacted_at).days >= config.OBSERVATION_WINDOW_DAYS:
            return {"action": "Handed to human review", "stage": "formal", "message": None, "nature": "exhaust"}
        # Inside the window the engine's bare return sends nothing.
        return {"action": "No automated action", "stage": "formal", "message": None, "nature": "schedule_return"}

    score = reliability.score_customer(invoice.customer_id, session, persist=False)
    target = _reliability_band_stage(days_overdue, score)
    has_broken_promise = any(p.status == PromiseStatus.broken for p in (invoice.promises or []))
    if has_broken_promise:
        target = EscalationStage.formal if score <= config.LOW_RELIABILITY_THRESHOLD else EscalationStage.firm
    if _STAGE_SEVERITY[target] < _STAGE_SEVERITY[invoice.current_stage]:
        target = invoice.current_stage
    if target == invoice.current_stage:
        if not invoice.last_contacted_at or (now_ts - invoice.last_contacted_at).days < config.RECONTACT_INTERVAL_DAYS:
            return {"action": "No automated action", "stage": target.value, "message": None, "nature": "schedule_return"}

    if has_broken_promise:
        label = {
            EscalationStage.firm: "Send firm reminder for broken commitment",
            EscalationStage.formal: "Send formal notice for broken commitment",
        }[target]
    else:
        label = {
            EscalationStage.nudge: "Send friendly nudge",
            EscalationStage.firm: "Send firm reminder",
            EscalationStage.formal: "Send formal notice",
        }[target]
    return {"action": label, "stage": target.value, "message": _format_message(invoice, target), "nature": "ladder_send"}


def _ensure_payment_link(session: Session, invoice: Invoice, amount: float | None = None) -> dict:
    """Provision Razorpay rails once and write the resulting action to the ledger."""
    if invoice.razorpay_payment_link_id:
        payment_link_id = invoice.razorpay_payment_link_id
        return {"id": payment_link_id, "short_url": f"https://rzp.io/{payment_link_id}", "mocked": "mock" in payment_link_id}
    if not invoice.razorpay_invoice_id:
        provider_invoice = razorpay_client.create_invoice(invoice)
        invoice.razorpay_invoice_id = provider_invoice.get("id")
        session.commit()
        ledger_engine.append_entry(
            session, invoice.id, LedgerEventType.invoice_created,
            {"provider": "Razorpay", "razorpay_invoice_id": provider_invoice.get("id"), "mocked": bool(provider_invoice.get("mocked", False))},
        )
    link = razorpay_client.create_payment_link(invoice) if amount is None else razorpay_client.create_payment_link(invoice, amount=amount)
    invoice.razorpay_payment_link_id = link.get("id")
    session.commit()
    ledger_engine.append_entry(
        session, invoice.id, LedgerEventType.payment_link_created,
        {"provider": "Razorpay", "payment_link_id": link.get("id"), "payment_link": link.get("short_url"), "amount": amount or invoice.amount, "mocked": bool(link.get("mocked", False))},
    )
    return link
