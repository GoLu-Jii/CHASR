from datetime import datetime, timedelta

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.engines import escalation
from backend.models import Base, Customer, Invoice, InvoiceStatus, Ledger, LedgerEventType, Promise, PromiseConfidence, PromiseStatus


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


def test_expired_commitments_escalate_without_rewriting_dates(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    reference_time = datetime(2026, 9, 11)
    customer = Customer(name="Promise Co", phone="1", email="promise@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(customer_id=customer.id, amount=1000, due_date=reference_time - timedelta(days=20), status=InvoiceStatus.unpaid)
    session.add(invoice)
    session.flush()
    first_date = reference_time - timedelta(days=4)
    second_date = reference_time + timedelta(days=2)
    session.add_all([
        Promise(invoice_id=invoice.id, amount=500, promised_date=first_date, confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="First promise"),
        Promise(invoice_id=invoice.id, amount=500, promised_date=second_date, confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="Second promise"),
    ])
    session.commit()
    monkeypatch.setattr(escalation, "now", lambda: reference_time)
    monkeypatch.setattr(escalation.razorpay_client, "create_invoice", lambda invoice: {"id": "invoice_mock", "mocked": True})
    monkeypatch.setattr(escalation.razorpay_client, "create_payment_link", lambda invoice: {"id": "link_mock", "short_url": "https://rzp.io/mock", "mocked": True})

    escalation.evaluate_and_escalate(session, invoice.id)
    promises = session.query(Promise).filter(Promise.invoice_id == invoice.id).order_by(Promise.id).all()

    assert promises[0].status == PromiseStatus.broken
    assert promises[1].status == PromiseStatus.pending
    assert promises[0].promised_date == first_date
    assert promises[1].promised_date == second_date
    assert invoice.current_stage == escalation.EscalationStage.formal


def test_expired_dated_commitment_is_escalated_when_other_commitment_needs_review(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    reference_time = datetime(2026, 9, 11)
    customer = Customer(name="Incomplete Promise Co", phone="1", email="incomplete@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(customer_id=customer.id, amount=1000, due_date=reference_time - timedelta(days=20), status=InvoiceStatus.unpaid, needs_review=True)
    session.add(invoice)
    session.flush()
    dated = Promise(invoice_id=invoice.id, amount=500, promised_date=reference_time - timedelta(days=4), confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="Dated promise")
    undated = Promise(invoice_id=invoice.id, amount=500, promised_date=None, confidence=PromiseConfidence.vague, status=PromiseStatus.pending, source_text="Undated promise")
    session.add_all([dated, undated])
    session.commit()
    monkeypatch.setattr(escalation, "now", lambda: reference_time)
    monkeypatch.setattr(escalation.razorpay_client, "create_invoice", lambda invoice: {"id": "invoice_mock", "mocked": True})
    monkeypatch.setattr(escalation.razorpay_client, "create_payment_link", lambda invoice: {"id": "link_mock", "short_url": "https://rzp.io/mock", "mocked": True})

    escalation.evaluate_and_escalate(session, invoice.id)
    session.refresh(dated)
    session.refresh(undated)

    assert dated.status == PromiseStatus.broken
    assert undated.status == PromiseStatus.pending
    assert invoice.current_stage == escalation.EscalationStage.formal


def test_expired_promise_respects_contact_ceiling_and_is_audited(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    reference_time = datetime(2026, 9, 11)
    customer = Customer(name="Capped Promise Co", phone="1", email="cap@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(customer_id=customer.id, amount=1000, due_date=reference_time - timedelta(days=20), status=InvoiceStatus.unpaid)
    session.add(invoice)
    session.flush()
    session.add(Promise(invoice_id=invoice.id, amount=1000, promised_date=reference_time - timedelta(days=3), confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="Will pay"))
    session.commit()
    monkeypatch.setattr(escalation, "now", lambda: reference_time)
    for _ in range(6):
        from backend.engines import ledger
        ledger.append_entry(session, invoice.id, LedgerEventType.escalation_sent, {"stage": "nudge"})

    escalation.evaluate_and_escalate(session, invoice.id)
    session.refresh(invoice)
    promise = session.query(Promise).filter_by(invoice_id=invoice.id).one()

    assert promise.status == PromiseStatus.broken
    assert invoice.status == InvoiceStatus.escalation_exhausted
    assert session.query(Ledger).filter(Ledger.event_type == LedgerEventType.promise_status_updated).count() == 1


def test_promise_is_broken_on_the_day_after_its_stated_date(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    reference_time = datetime(2026, 9, 13, 7, 0)
    customer = Customer(name="Deadline Co", phone="1", email="deadline@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(customer_id=customer.id, amount=1000, due_date=reference_time - timedelta(days=20), status=InvoiceStatus.unpaid)
    session.add(invoice)
    session.flush()
    promise = Promise(invoice_id=invoice.id, amount=1000, promised_date=datetime(2026, 9, 12), confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="Will pay by 12 September")
    session.add(promise)
    session.commit()
    monkeypatch.setattr(escalation, "now", lambda: reference_time)
    monkeypatch.setattr(escalation.reliability, "score_customer", lambda *args, **kwargs: 0.2)
    monkeypatch.setattr(escalation.razorpay_client, "create_invoice", lambda invoice: {"id": "invoice_mock", "mocked": True})
    monkeypatch.setattr(escalation.razorpay_client, "create_payment_link", lambda invoice: {"id": "link_mock", "short_url": "https://rzp.io/mock", "mocked": True})

    escalation.evaluate_and_escalate(session, invoice.id)
    session.refresh(promise)
    session.refresh(invoice)

    assert promise.status == PromiseStatus.broken
    assert promise.promised_date == datetime(2026, 9, 12)
    assert invoice.current_stage == escalation.EscalationStage.formal


def test_broken_promise_low_reliability_escalates_formal(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    reference_time = datetime(2026, 9, 13)
    customer = Customer(name="Risky Promise Co", phone="1", email="risky@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(customer_id=customer.id, amount=1000, due_date=reference_time - timedelta(days=20), status=InvoiceStatus.unpaid)
    session.add(invoice)
    session.flush()
    session.add(Promise(invoice_id=invoice.id, amount=1000, promised_date=reference_time - timedelta(days=1), confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="Will pay"))
    session.commit()
    monkeypatch.setattr(escalation, "now", lambda: reference_time)
    monkeypatch.setattr(escalation.reliability, "score_customer", lambda *args, **kwargs: 0.2)
    monkeypatch.setattr(escalation.razorpay_client, "create_invoice", lambda invoice: {"id": "invoice_mock", "mocked": True})
    monkeypatch.setattr(escalation.razorpay_client, "create_payment_link", lambda invoice: {"id": "link_mock", "short_url": "https://rzp.io/mock", "mocked": True})

    escalation.evaluate_and_escalate(session, invoice.id)
    session.refresh(invoice)
    assert invoice.current_stage == escalation.EscalationStage.formal
    assert session.query(Promise).filter_by(invoice_id=invoice.id).one().status == PromiseStatus.broken


def test_broken_promise_high_reliability_escalates_firm(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    reference_time = datetime(2026, 9, 13)
    customer = Customer(name="Reliable Promise Co", phone="1", email="reliable@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(customer_id=customer.id, amount=1000, due_date=reference_time - timedelta(days=20), status=InvoiceStatus.unpaid)
    session.add(invoice)
    session.flush()
    session.add(Promise(invoice_id=invoice.id, amount=1000, promised_date=reference_time - timedelta(days=1), confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="Will pay"))
    session.commit()
    monkeypatch.setattr(escalation, "now", lambda: reference_time)
    monkeypatch.setattr(escalation.reliability, "score_customer", lambda *args, **kwargs: 0.8)
    monkeypatch.setattr(escalation.razorpay_client, "create_invoice", lambda invoice: {"id": "invoice_mock", "mocked": True})
    monkeypatch.setattr(escalation.razorpay_client, "create_payment_link", lambda invoice: {"id": "link_mock", "short_url": "https://rzp.io/mock", "mocked": True})

    escalation.evaluate_and_escalate(session, invoice.id)
    session.refresh(invoice)
    assert invoice.current_stage == escalation.EscalationStage.firm
    assert session.query(Promise).filter_by(invoice_id=invoice.id).one().status == PromiseStatus.broken


def test_next_action_expired_promise_is_not_masked_by_incomplete(monkeypatch):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = sessionmaker(bind=engine)()
    reference_time = datetime(2026, 9, 13)
    customer = Customer(name="Mixed Promise Co", phone="1", email="mixed@example.test")
    session.add(customer)
    session.flush()
    invoice = Invoice(customer_id=customer.id, amount=1000, due_date=reference_time - timedelta(days=20), status=InvoiceStatus.unpaid)
    session.add(invoice)
    session.flush()
    session.add_all([
        Promise(invoice_id=invoice.id, amount=500, promised_date=reference_time - timedelta(days=1), confidence=PromiseConfidence.firm, status=PromiseStatus.pending, source_text="Dated tranche"),
        Promise(invoice_id=invoice.id, amount=500, promised_date=None, confidence=PromiseConfidence.vague, status=PromiseStatus.pending, source_text="No date tranche"),
    ])
    session.commit()
    monkeypatch.setattr(escalation, "now", lambda: reference_time)
    monkeypatch.setattr(escalation.reliability, "score_customer", lambda *args, **kwargs: 0.2)

    decision = escalation.next_action(session, invoice)
    assert decision["nature"] == "broken_send"
    assert decision["action"] == "Mark broken and send notice"
    assert decision["stage"] == "formal"
