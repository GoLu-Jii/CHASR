from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.engines import escalation
from backend.models import Base, Customer, Invoice, InvoiceStatus, Ledger, LedgerEventType


def test_low_reliability_customer_escalates_earlier(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    customer = Customer(name="Risky", phone="1", email="risk@example.test")
    session.add(customer)
    session.flush()
    reference_time = datetime(2026, 9, 4)
    invoice = Invoice(customer_id=customer.id, amount=1000, due_date=reference_time - timedelta(days=8), status=InvoiceStatus.unpaid)
    session.add(invoice)
    session.commit()

    monkeypatch.setattr(escalation, "now", lambda: reference_time)
    monkeypatch.setattr(escalation.reliability, "score_customer", lambda *args, **kwargs: 0.2)
    monkeypatch.setattr(escalation.razorpay_client, "create_invoice", lambda invoice: {"id": "invoice_mock", "mocked": True})
    monkeypatch.setattr(escalation.razorpay_client, "create_payment_link", lambda invoice: {"id": "link_mock", "short_url": "https://rzp.io/mock", "mocked": True})

    escalation.evaluate_and_escalate(session, invoice.id)
    session.refresh(invoice)
    assert invoice.current_stage.value == "firm"
    assert invoice.contact_count == 1
    assert session.query(Ledger).filter(Ledger.event_type == LedgerEventType.payment_link_created).count() == 1
