from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.engines.ledger import append_entry, verify_chain
from backend.models import Base, Customer, Invoice, Ledger, LedgerEventType


def test_ledger_detects_payload_tampering():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    customer = Customer(name="Acme", phone="1", email="a@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(customer_id=customer.id, amount=100, due_date=datetime.utcnow())
    session.add(invoice)
    session.commit()

    append_entry(session, invoice.id, LedgerEventType.invoice_created, {"amount": 100})
    append_entry(session, invoice.id, LedgerEventType.escalation_sent, {"stage": "nudge"})
    assert verify_chain(session, invoice.id) is True

    entry = session.query(Ledger).filter(Ledger.invoice_id == invoice.id).first()
    entry.payload = {"amount": 999}
    session.commit()
    assert verify_chain(session, invoice.id) is False
