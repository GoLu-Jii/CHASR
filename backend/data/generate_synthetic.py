# backend/data/generate_synthetic.py

import random
import numpy as np
from datetime import datetime, timedelta

from backend.database import SessionLocal, init_db
from backend.models import Customer, Invoice, Promise, InvoiceStatus, EscalationStage, LedgerEventType, PromiseConfidence, PromiseStatus
from backend.engines import ledger as ledger_engine
from backend import config

# LOWERED from 0.4 to 0.15. If they fail the honesty roll, they break the promise.
PARTIAL_INSTEAD_OF_BROKEN_PROB = 0.15

def determine_tone(base_honesty):
    """
    Determines the tone of the promise probabilistically based on base honesty.
    Slippery customers fake high confidence; struggling ones sound vague.
    """
    if base_honesty > 0.8:
        return random.choices([PromiseConfidence.firm, PromiseConfidence.soft], weights=[0.8, 0.2])[0]
    elif base_honesty > 0.4:
        return random.choices([PromiseConfidence.soft, PromiseConfidence.vague], weights=[0.6, 0.4])[0]
    else:
        # The serial slippery: low honesty, high confidence
        return random.choices([PromiseConfidence.firm, PromiseConfidence.vague], weights=[0.7, 0.3])[0]

def generate_customers_and_history(session, num_customers=1000):
    print(f"Generating {num_customers} unique synthetic customers using continuous distributions...")
    
    for i in range(num_customers):
        # Continuous Variance: Every customer gets a unique profile
        base_honesty = float(np.clip(np.random.normal(loc=0.65, scale=0.25), 0.1, 0.99))
        base_responsiveness = float(np.clip(np.random.normal(loc=0.60, scale=0.30), 0.1, 0.99))
        
        base_delay_days = int(np.random.gamma(shape=2.0, scale=10.0))
        base_delay_days = max(1, min(base_delay_days, 90))
        
        behavior = {
            "honesty": base_honesty,
            "responsiveness": base_responsiveness,
            "delay_days": base_delay_days
        }

        tenure_days = random.randint(400, 700)
        created_at = datetime.utcnow() - timedelta(days=tenure_days)

        customer = Customer(
            name=f"Customer {i+1}", 
            email=f"accounts@company{i+1}.com",
            phone=f"+9198765{random.randint(10000, 99999)}",
            created_at=created_at,
        )
        session.add(customer)
        session.commit()
        
        # 15-25 invoices per customer to cure the cold-start penalty
        generate_invoices_for_customer(session, customer, behavior, tenure_days)

def generate_invoices_for_customer(session, customer, behavior, tenure_days):
    num_invoices = random.randint(15, 25)

    for _ in range(num_invoices):
        days_ago = random.randint(30, tenure_days - 30)
        issued_date = datetime.utcnow() - timedelta(days=days_ago)

        invoice = Invoice(
            customer_id=customer.id,
            amount=round(random.uniform(10000, 500000), 2),
            amount_paid=0.0,
            due_date=issued_date + timedelta(days=30),
            issued_date=issued_date,
            status=InvoiceStatus.unpaid,
        )
        session.add(invoice)
        session.commit()

        ledger_engine.append_entry(
            session, invoice.id, LedgerEventType.invoice_created,
            {"msg": "Invoice generated via Razorpay (test mode)"},
        )
        simulate_invoice_lifecycle(session, invoice, behavior)

def simulate_invoice_lifecycle(session, invoice, behavior):
    if random.random() >= behavior["responsiveness"]:
        return

    escalation_entry = ledger_engine.append_entry(
        session, invoice.id, LedgerEventType.escalation_sent,
        {"stage": "nudge", "channel": "WhatsApp (Simulated)", "note": "synthetic historical escalation"},
    )

    tone = determine_tone(behavior["honesty"])
    
    delay_variance = random.randint(-5, 5)
    actual_delay = max(1, behavior["delay_days"] + delay_variance)
    promised_date = invoice.due_date + timedelta(days=actual_delay)

    outcome_roll = random.random()
    if outcome_roll < behavior["honesty"]:
        payment_amount = invoice.amount * random.uniform(0.95, 1.0)
    elif outcome_roll < behavior["honesty"] + (1 - behavior["honesty"]) * PARTIAL_INSTEAD_OF_BROKEN_PROB:
        payment_amount = invoice.amount * random.uniform(0.30, 0.94)
    else:
        payment_amount = invoice.amount * random.uniform(0.0, 0.29)

    invoice.amount_paid = round(payment_amount, 2)
    payment_ratio = invoice.amount_paid / invoice.amount
    if payment_ratio >= config.KEPT_MIN_PCT:
        final_status = PromiseStatus.kept_full
    elif payment_ratio >= config.PARTIAL_MIN_PCT:
        final_status = PromiseStatus.kept_partial
    else:
        final_status = PromiseStatus.broken
    if final_status == PromiseStatus.kept_full:
        invoice.status = InvoiceStatus.paid
    elif final_status == PromiseStatus.kept_partial:
        invoice.status = InvoiceStatus.partially_paid
    else:
        invoice.status = InvoiceStatus.written_off
        invoice.current_stage = EscalationStage.formal
    session.commit()

    promise = Promise(
        invoice_id=invoice.id, ledger_entry_id=escalation_entry.id,
        amount=invoice.amount, promised_date=promised_date,
        confidence=tone, status=final_status,
        source_text="Simulated reply placeholder — real text arrives once promise_extraction.py exists",
    )
    session.add(promise)
    session.commit()

    ledger_engine.append_entry(
        session, invoice.id, LedgerEventType.reply_received,
        {"text": "Synthetic historical reply"},
    )
    ledger_engine.append_entry(
        session, invoice.id, LedgerEventType.promise_extracted,
        {
            "amount": invoice.amount,
            "promised_date": promised_date.isoformat(),
            "confidence": tone.value,
        },
    )
    ledger_engine.append_entry(
        session, invoice.id, LedgerEventType.promise_status_updated,
        {"status": final_status.value, "promised_date": promised_date.isoformat()},
    )
    if invoice.amount_paid > 0:
        ledger_engine.append_entry(session, invoice.id, LedgerEventType.payment_received, {"amount": invoice.amount_paid})

if __name__ == "__main__":
    init_db()
    session = SessionLocal()
    try:
        generate_customers_and_history(session, num_customers=1000)
        print("Database populated successfully. Synthetic baseline established with continuous distributions.")
    finally:
        session.close()