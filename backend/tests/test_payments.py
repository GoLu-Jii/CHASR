from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.engines.payments import apply_payment
from backend.models import Base, Customer, Invoice, InvoiceStatus, Promise, PromiseConfidence, PromiseStatus


def test_full_payment_closes_multiple_commitments():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    customer = Customer(name="Acme", phone="1", email="acme@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(
        customer_id=customer.id,
        amount=100000,
        due_date=datetime.utcnow() - timedelta(days=10),
        status=InvoiceStatus.unpaid,
    )
    session.add(invoice)
    session.flush()
    session.add_all([
        Promise(invoice_id=invoice.id, amount=50000, confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="First tranche"),
        Promise(invoice_id=invoice.id, amount=50000, confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="Final tranche"),
    ])
    session.commit()

    apply_payment(session, invoice, 100000, "razorpay_sync")
    session.refresh(invoice)

    assert invoice.status == InvoiceStatus.paid
    assert session.query(Promise).filter(Promise.invoice_id == invoice.id, Promise.status == PromiseStatus.pending).count() == 0
    assert session.query(Promise).filter(Promise.invoice_id == invoice.id, Promise.status == PromiseStatus.kept_full).count() == 2


def test_full_payment_closes_duplicate_commitments():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    customer = Customer(name="Duplicate Reply Co", phone="1", email="duplicate@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(customer_id=customer.id, amount=100000, due_date=datetime.utcnow(), status=InvoiceStatus.unpaid)
    session.add(invoice)
    session.flush()
    session.add_all([
        Promise(invoice_id=invoice.id, amount=50000, confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="Repeated reply")
        for _ in range(4)
    ])
    session.commit()

    apply_payment(session, invoice, 100000, "razorpay_sync")

    assert invoice.status == InvoiceStatus.paid
    assert session.query(Promise).filter(Promise.invoice_id == invoice.id, Promise.status == PromiseStatus.pending).count() == 0
    assert session.query(Promise).filter(Promise.invoice_id == invoice.id, Promise.status == PromiseStatus.kept_full).count() == 4