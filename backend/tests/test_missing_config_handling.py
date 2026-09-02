from datetime import datetime

from backend.models import Invoice, Customer
from backend.integrations.razorpay_client import create_invoice, create_payment_link
from backend.engines.promise_extraction import extract_promise


def make_invoice():
    customer = Customer(name="Acme Labs", phone="9999999999", email="ops@acme.test")
    invoice = Invoice(
        customer=customer,
        amount=25000,
        due_date=datetime(2026, 9, 15),
        status="unpaid",
    )
    return invoice


def test_razorpay_mock_invoice_without_keys():
    invoice = make_invoice()
    data = create_invoice(invoice)
    assert data["status"] in {"issued", "mocked"}
    assert "short_url" in data


def test_razorpay_mock_payment_link_without_keys():
    invoice = make_invoice()
    data = create_payment_link(invoice)
    assert data["status"] in {"issued", "mocked"}
    assert "short_url" in data


def test_promise_extraction_handles_missing_api_key(session=None):
    invoice = make_invoice()
    result = extract_promise(session, 1, "We will pay ₹5000 by Friday")
    assert result == []
