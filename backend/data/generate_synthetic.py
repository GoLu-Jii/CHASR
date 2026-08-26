# backend/data/generate_synthetic.py

import random
from datetime import datetime, timedelta
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Import the models we just built
from backend.models import (
    Base, Customer, Invoice, Ledger, Promise, CustomerReliability,
    InvoiceStatus, EscalationStage, LedgerEventType, PromiseConfidence, PromiseStatus
)

# Setup SQLite Database
engine = create_engine("sqlite:///chasr.db")
Base.metadata.create_all(engine)
Session = sessionmaker(bind=engine)
session = Session()

# ==========================================
# 1. The 5 Behavioral Archetypes
# ==========================================
ARCHETYPES = {
    "Reliable": {"honesty": 0.9, "responsiveness": 0.9, "delay_days": 2, "tone": [PromiseConfidence.firm]},
    "Slow-but-honest": {"honesty": 0.85, "responsiveness": 0.6, "delay_days": 15, "tone": [PromiseConfidence.firm, PromiseConfidence.soft]},
    "Cash-strapped-genuine": {"honesty": 0.55, "responsiveness": 0.7, "delay_days": 25, "tone": [PromiseConfidence.soft, PromiseConfidence.vague]},
    "Serial-slippery": {"honesty": 0.25, "responsiveness": 0.7, "delay_days": 40, "tone": [PromiseConfidence.firm]}, # High confidence, low honesty
    "Ghost": {"honesty": 0.4, "responsiveness": 0.2, "delay_days": 60, "tone": [PromiseConfidence.vague]}
}

# ==========================================
# 2. Generator Functions
# ==========================================

def generate_customers_and_history(num_customers=50):
    print(f"Generating {num_customers} synthetic customers...")
    
    archetype_keys = list(ARCHETYPES.keys())
    
    for i in range(num_customers):
        # Assign a hidden archetype (not saved to DB, only used for data generation)
        archetype_name = random.choice(archetype_keys)
        behavior = ARCHETYPES[archetype_name]
        
        customer = Customer(
            name=f"Customer {i+1} ({archetype_name})", # Name includes archetype just for your easy debugging
            email=f"accounts@company{i+1}.com",
            phone=f"+9198765{random.randint(10000, 99999)}"
        )
        session.add(customer)
        session.commit()
        
        # Generate 5-10 historical invoices per customer
        generate_invoices_for_customer(customer, behavior)

def generate_invoices_for_customer(customer, behavior):
    num_invoices = random.randint(5, 10)
    
    for _ in range(num_invoices):
        amount = round(random.uniform(10000, 500000), 2)
        # Random past date between 1 year ago and 1 month ago
        days_ago = random.randint(30, 365)
        issued_date = datetime.utcnow() - timedelta(days=days_ago)
        due_date = issued_date + timedelta(days=30) # Net-30 terms
        
        invoice = Invoice(
            customer_id=customer.id,
            amount=amount,
            due_date=due_date,
            issued_date=issued_date,
            status=InvoiceStatus.unpaid # We start unpaid, and simulate history
        )
        session.add(invoice)
        session.commit()
        
        # Simulate the invoice's lifecycle based on customer archetype
        simulate_invoice_lifecycle(invoice, behavior)

def simulate_invoice_lifecycle(invoice, behavior):
    # Base ledger entry for invoice creation
    ledger_create = Ledger(
        invoice_id=invoice.id,
        event_type=LedgerEventType.invoice_created,
        payload={"msg": "Invoice generated via Razorpay"},
        prev_hash="0" * 64, # Genesis hash
        hash=f"mock_hash_{random.randint(1000, 9999)}" # Mocking hash for generator script
    )
    session.add(ledger_create)
    session.commit()
    
    # Check if they reply to escalations (Responsiveness)
    if random.random() < behavior["responsiveness"]:
        tone = random.choice(behavior["tone"])
        promised_date = invoice.due_date + timedelta(days=behavior["delay_days"])
        
        # Determine actual outcome based strictly on HONESTY, not TONE
        # This is the golden rule from the architecture doc.
        is_kept = random.random() < behavior["honesty"]
        
        if is_kept:
            final_status = PromiseStatus.kept_full
            invoice.status = InvoiceStatus.paid
        else:
            final_status = PromiseStatus.broken
            invoice.status = InvoiceStatus.unpaid
            invoice.current_stage = EscalationStage.formal
            
        promise = Promise(
            invoice_id=invoice.id,
            ledger_entry_id=ledger_create.id,
            amount=invoice.amount,
            promised_date=promised_date,
            confidence=tone,
            status=final_status,
            source_text="Simulated email reply placeholder"
        )
        session.add(promise)
        session.commit()

if __name__ == "__main__":
    generate_customers_and_history(50)
    print("Database populated successfully. Synthetic baseline established.")