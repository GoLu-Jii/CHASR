# backend/models.py

import enum
from datetime import datetime
from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Enum, JSON
from sqlalchemy.orm import declarative_base, relationship

Base = declarative_base()


class InvoiceStatus(enum.Enum):
    unpaid = "unpaid"
    partially_paid = "partially_paid"
    paid = "paid"
    written_off = "written_off"

class EscalationStage(enum.Enum):
    none = "none"
    nudge = "nudge"
    firm = "firm"
    formal = "formal"

class LedgerEventType(enum.Enum):
    invoice_created = "invoice_created"
    escalation_sent = "escalation_sent"
    reply_received = "reply_received"
    promise_extracted = "promise_extracted"
    promise_status_updated = "promise_status_updated"
    payment_link_created = "payment_link_created"
    payment_received = "payment_received"
    escalated_to_human_review = "escalated_to_human_review"

class PromiseConfidence(enum.Enum):
    firm = "firm"
    soft = "soft"
    vague = "vague"

class PromiseStatus(enum.Enum):
    pending = "pending"
    kept_full = "kept_full"
    kept_partial = "kept_partial"
    broken = "broken"


class Customer(Base):
    __tablename__ = "customers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    gstin = Column(String, nullable=True)
    phone = Column(String)
    email = Column(String)
    created_at = Column(DateTime, default=datetime.utcnow)

    invoices = relationship("Invoice", back_populates="customer")
    reliability_scores = relationship("CustomerReliability", back_populates="customer")


class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    amount = Column(Float, nullable=False)
    due_date = Column(DateTime, nullable=False)
    issued_date = Column(DateTime, default=datetime.utcnow)
    
    # Links directly to the real test-mode Razorpay object
    razorpay_invoice_id = Column(String, unique=True, index=True, nullable=True)
    
    status = Column(Enum(InvoiceStatus), default=InvoiceStatus.unpaid)
    current_stage = Column(Enum(EscalationStage), default=EscalationStage.none)
    last_contacted_at = Column(DateTime, nullable=True)

    customer = relationship("Customer", back_populates="invoices")
    ledger_entries = relationship("Ledger", back_populates="invoice")
    promises = relationship("Promise", back_populates="invoice")


class Ledger(Base):
    """
    The core audit trail. Append-only by construction. 
    Never UPDATE or DELETE rows in this table.
    """
    __tablename__ = "ledger"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    event_type = Column(Enum(LedgerEventType), nullable=False)
    
    # Stores the raw API response, email text, or LLM extraction JSON
    payload = Column(JSON, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # SHA-256 Chaining Fields
    prev_hash = Column(String, nullable=False)
    hash = Column(String, nullable=False, unique=True)

    invoice = relationship("Invoice", back_populates="ledger_entries")
    promises = relationship("Promise", back_populates="ledger_entry")


class Promise(Base):
    __tablename__ = "promises"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(Integer, ForeignKey("invoices.id"))
    ledger_entry_id = Column(Integer, ForeignKey("ledger.id"))
    
    amount = Column(Float, nullable=True)
    promised_date = Column(DateTime, nullable=True)
    confidence = Column(Enum(PromiseConfidence), nullable=False)
    status = Column(Enum(PromiseStatus), default=PromiseStatus.pending)
    
    # The raw text the LLM parsed this from
    source_text = Column(String, nullable=False)

    invoice = relationship("Invoice", back_populates="promises")
    ledger_entry = relationship("Ledger", back_populates="promises")


class CustomerReliability(Base):

    __tablename__ = "customer_reliability"

    id = Column(Integer, primary_key=True, index=True)
    customer_id = Column(Integer, ForeignKey("customers.id"))
    computed_at = Column(DateTime, default=datetime.utcnow)
    
    total_promises = Column(Integer, default=0)
    kept_full = Column(Integer, default=0)
    kept_partial = Column(Integer, default=0)
    broken = Column(Integer, default=0)
    
    kept_full_rate = Column(Float, default=0.0)
    broken_rate = Column(Float, default=0.0)
    avg_days_late = Column(Float, default=0.0)
    
    # Output of the LogisticRegression model (0.0 to 1.0)
    score = Column(Float, default=0.0)

    customer = relationship("Customer", back_populates="reliability_scores")