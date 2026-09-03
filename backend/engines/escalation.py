# backend/engines/escalation.py

from datetime import datetime
from sqlalchemy.orm import Session

from backend.clock import now
from backend.models import (
    Invoice, InvoiceStatus, EscalationStage,
    Promise, PromiseStatus, Ledger, LedgerEventType,
)
from backend.engines import ledger as ledger_engine
from backend import config

TEMPLATES = {
    EscalationStage.nudge: "Hi {name}, friendly reminder that invoice {inv_id} for {amount} was due on {date}. Could you let us know when it might be cleared?",
    EscalationStage.firm: "Hi {name}, invoice {inv_id} for {amount} is now significantly overdue. Please process this payment immediately via this link: {link}",
    EscalationStage.formal: "ATTENTION: Invoice {inv_id} is severely overdue. Further delay will result in account suspension and formal legal routing. Pay immediately: {link}",
}

_TERMINAL_STATUSES = {InvoiceStatus.paid, InvoiceStatus.written_off, InvoiceStatus.escalation_exhausted}


def evaluate_and_escalate(session: Session, invoice_id: int):
    invoice = session.query(Invoice).filter(
        Invoice.id == invoice_id,
        Invoice.status.in_([InvoiceStatus.unpaid, InvoiceStatus.partially_paid]),
    ).first()

    if not invoice or invoice.status in _TERMINAL_STATUSES:
        return

    if invoice.needs_review:
        return

    active_promise = (
        session.query(Promise)
        .filter(Promise.invoice_id == invoice_id, Promise.status == PromiseStatus.pending)
        .order_by(Promise.promised_date.asc())
        .first()
    )

    if active_promise:
        if active_promise.promised_date is None:
            invoice.needs_review = True
            session.commit()
            return
        if active_promise.promised_date >= now():
            return  # STOPPING RULE 2 — inside the agreed grace period

        # Broken promise — fast-track to formal and stop HERE. Do not fall
        # through to the days-overdue calc below, which could compute a
        # lower stage and silently undo this.
        active_promise.status = PromiseStatus.broken
        session.commit()
        _execute_escalation(session, invoice, EscalationStage.formal)
        return

    days_overdue = (now() - invoice.due_date).days
    if days_overdue <= config.NUDGE_AFTER_DAYS:
        return

    contact_count = (
        session.query(Ledger)
        .filter(Ledger.invoice_id == invoice_id, Ledger.event_type == LedgerEventType.escalation_sent)
        .count()
    )
    if contact_count >= config.MAX_AUTOMATED_CONTACTS:
        _exhaust(session, invoice, reason=f"Hit the {config.MAX_AUTOMATED_CONTACTS}-contact ceiling.")
        return

    if invoice.current_stage == EscalationStage.formal and invoice.last_contacted_at:
        silence_days = (now() - invoice.last_contacted_at).days
        if silence_days >= config.OBSERVATION_WINDOW_DAYS:
            _exhaust(session, invoice, reason=f"No response {silence_days} days after formal notice.")
        return  # inside or past the window — either way, don't re-send formal on repeat

    target_stage = EscalationStage.nudge
    has_broken_promise = session.query(Promise).filter(
        Promise.invoice_id == invoice_id,
        Promise.status == PromiseStatus.broken,
    ).first() is not None
    if has_broken_promise or days_overdue > config.FORMAL_AFTER_DAYS:
        target_stage = EscalationStage.formal
    elif days_overdue > config.FIRM_AFTER_DAYS:
        target_stage = EscalationStage.firm

    severity = {
        EscalationStage.none: 0,
        EscalationStage.nudge: 1,
        EscalationStage.firm: 2,
        EscalationStage.formal: 3,
    }
    if severity[target_stage] < severity[invoice.current_stage]:
        target_stage = invoice.current_stage

    if target_stage == invoice.current_stage:
        return  # already sent this stage — this is what stops the daily-resend bug

    _execute_escalation(session, invoice, target_stage)


def _exhaust(session: Session, invoice: Invoice, reason: str):
    invoice.status = InvoiceStatus.escalation_exhausted
    session.commit()
    ledger_engine.append_entry(session, invoice.id, LedgerEventType.escalated_to_human_review, {"reason": reason})


def _execute_escalation(session: Session, invoice: Invoice, stage: EscalationStage):
    customer = invoice.customer
    mock_link = f"https://rzp.io/test_{invoice.id}"  # stubbed until razorpay_client.py exists

    message = TEMPLATES[stage].format(
        name=customer.name, inv_id=invoice.id, amount=invoice.amount,
        date=invoice.due_date.strftime("%Y-%m-%d"), link=mock_link,
    )

    invoice.current_stage = stage
    invoice.last_contacted_at = now()
    session.commit()

    ledger_engine.append_entry(
        session=session, invoice_id=invoice.id, event_type=LedgerEventType.escalation_sent,
        payload={"stage": stage.value, "message_sent": message, "channel": "WhatsApp (Simulated)", "payment_link": mock_link},
    )
