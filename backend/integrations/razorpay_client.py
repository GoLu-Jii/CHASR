# backend/integrations/razorpay_client.py

import time
from datetime import datetime

import razorpay

from backend import config
from backend.models import Invoice


def get_client():
    if not config.RAZORPAY_KEY_ID or not config.RAZORPAY_KEY_SECRET:
        return None
    return razorpay.Client(auth=(config.RAZORPAY_KEY_ID, config.RAZORPAY_KEY_SECRET))


def _mock_response(invoice_record: Invoice, kind: str = "invoice") -> dict:
    safe_id = getattr(invoice_record, "id", "new")
    return {
        "id": f"{kind}_mock_{safe_id}",
        "short_url": f"https://rzp.io/mock_{kind}_{safe_id}",
        "status": "issued",
        "mocked": True,
    }


def create_invoice(invoice_record: Invoice) -> dict:
    """Create a test-mode Razorpay invoice for an overdue B2B invoice."""
    client = get_client()
    if client is None:
        return _mock_response(invoice_record, kind="invoice")

    customer = invoice_record.customer
    amount_in_paise = int(float(invoice_record.amount) * 100)
    due_date_ts = int(time.mktime(invoice_record.due_date.timetuple()))

    payload = {
        "type": "invoice",
        "description": f"B2B Software Services - Ref #{invoice_record.id}",
        "customer": {
            "name": customer.name,
            "contact": customer.phone,
            "email": customer.email,
        },
        "line_items": [{
            "name": "Enterprise SaaS License",
            "description": "Monthly Net-30 Billing",
            "amount": amount_in_paise,
            "currency": "INR",
            "quantity": 1,
        }],
        "sms_notify": 0,
        "email_notify": 0,
        "currency": "INR",
        "expire_by": due_date_ts + (30 * 24 * 60 * 60),
    }

    try:
        return client.invoice.create(data=payload)
    except Exception as exc:  # pragma: no cover - runtime guard for missing / invalid credentials
        print(f"Razorpay invoice creation failed: {exc}")
        return _mock_response(invoice_record, kind="invoice")


def create_payment_link(invoice_record: Invoice) -> dict:
    """Create a Razorpay payment link for a B2B invoice, or return a mock URL if not configured."""
    client = get_client()
    if client is None:
        return _mock_response(invoice_record, kind="link")

    try:
        payload = {
            "amount": int(float(invoice_record.amount) * 100),
            "currency": "INR",
            "description": f"Payment for invoice #{invoice_record.id}",
            "customer": {
                "name": invoice_record.customer.name,
                "contact": invoice_record.customer.phone,
                "email": invoice_record.customer.email,
            },
            "notify": {"sms": True, "email": False},
            "reminder_enable": True,
            "callback_url": "https://example.com/callback",
            "callback_method": "get",
        }
        return client.payment_link.create(data=payload)
    except Exception as exc:  # pragma: no cover
        print(f"Razorpay payment link creation failed: {exc}")
        return _mock_response(invoice_record, kind="link")


def create_real_invoice(invoice_record: Invoice) -> dict:
    return create_invoice(invoice_record)


def check_payment_status(razorpay_invoice_id: str) -> dict:
    if not razorpay_invoice_id or "mock" in razorpay_invoice_id:
        return {"status": "unpaid", "amount_paid": 0.0}

    client = get_client()
    if client is None:
        return {"status": "unpaid", "amount_paid": 0.0}

    try:
        rzp_invoice = client.invoice.fetch(razorpay_invoice_id)
        return {
            "status": rzp_invoice.get("status"),
            "amount_paid": float(rzp_invoice.get("amount_paid", 0)) / 100.0,
        }
    except Exception as exc:  # pragma: no cover
        print(f"Razorpay API Error fetching invoice {razorpay_invoice_id}: {exc}")
        return {"status": "unpaid", "amount_paid": 0.0}
