"""Payment reconciliation and promise-outcome updates."""

from sqlalchemy.orm import Session

from backend import config
from backend.clock import now
from backend.engines import ledger
from backend.models import Invoice, InvoiceStatus, LedgerEventType, Promise, PromiseStatus


def apply_payment(session: Session, invoice: Invoice, cumulative_amount_paid: float, source: str) -> Invoice:
    """Apply a cumulative receipt and allocate it across commitments in order."""
    paid = max(0.0, min(float(cumulative_amount_paid), float(invoice.amount)))
    previous_paid = float(invoice.amount_paid or 0)
    delta = round(paid - previous_paid, 2)
    invoice.amount_paid = paid
    if paid >= float(invoice.amount) * config.KEPT_MIN_PCT:
        invoice.status = InvoiceStatus.paid
    elif paid > 0:
        invoice.status = InvoiceStatus.partially_paid

    if delta > 0:
        session.commit()
        ledger.append_entry(session, invoice.id, LedgerEventType.payment_received, {"amount": delta, "cumulative_amount_paid": paid, "source": source})

    allocated = 0.0
    for promise in session.query(Promise).filter(Promise.invoice_id == invoice.id).order_by(Promise.id.asc()).all():
        expected = float(promise.amount or invoice.amount)
        promise_paid = expected if invoice.status == InvoiceStatus.paid else max(0.0, min(expected, paid - allocated))
        allocated += promise_paid
        ratio = promise_paid / expected if expected else 0.0
        previous_status = promise.status
        if ratio >= config.KEPT_MIN_PCT:
            new_status = PromiseStatus.kept_full
        elif ratio >= config.PARTIAL_MIN_PCT:
            new_status = PromiseStatus.kept_partial
        else:
            new_status = PromiseStatus.pending
        if new_status != previous_status:
            promise.status = new_status
            session.commit()
            ledger.append_entry(session, invoice.id, LedgerEventType.promise_status_updated, {
                "promise_id": promise.id, "status": promise.status.value, "evaluated_at": now().isoformat(),
            })
    session.commit()
    return invoice
