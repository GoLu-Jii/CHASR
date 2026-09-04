"""Payment reconciliation and promise-outcome updates."""

from sqlalchemy.orm import Session

from backend import config
from backend.clock import now
from backend.engines import ledger
from backend.models import Invoice, InvoiceStatus, LedgerEventType, Promise, PromiseStatus


def apply_payment(session: Session, invoice: Invoice, cumulative_amount_paid: float, source: str) -> Invoice:
    """Apply a cumulative receipt exactly once and update relevant promises."""
    paid = max(0.0, min(float(cumulative_amount_paid), float(invoice.amount)))
    if paid <= float(invoice.amount_paid or 0):
        return invoice

    delta = round(paid - float(invoice.amount_paid or 0), 2)
    invoice.amount_paid = paid
    invoice.status = InvoiceStatus.paid if paid >= float(invoice.amount) * config.KEPT_MIN_PCT else InvoiceStatus.partially_paid
    session.commit()
    ledger.append_entry(session, invoice.id, LedgerEventType.payment_received, {"amount": delta, "cumulative_amount_paid": paid, "source": source})

    for promise in session.query(Promise).filter(
        Promise.invoice_id == invoice.id, Promise.status == PromiseStatus.pending
    ).all():
        expected = float(promise.amount or invoice.amount)
        ratio = paid / expected if expected else 0.0
        if ratio >= config.KEPT_MIN_PCT:
            promise.status = PromiseStatus.kept_full
        elif ratio >= config.PARTIAL_MIN_PCT:
            promise.status = PromiseStatus.kept_partial
        else:
            continue
        session.commit()
        ledger.append_entry(session, invoice.id, LedgerEventType.promise_status_updated, {
            "promise_id": promise.id, "status": promise.status.value, "evaluated_at": now().isoformat(),
        })
    return invoice
